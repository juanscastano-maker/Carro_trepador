// Filtro de orientación de Mahony (acelerómetro + giroscopio, sin magnetómetro).
//
// El giroscopio da movimientos rápidos sin ruido pero se desvía con el tiempo; el acelerómetro
// sabe dónde está "abajo" pero se ensucia con la vibración de motores y turbinas. El filtro
// integra el giroscopio y lo corrige poco a poco hacia la gravedad que mide el acelerómetro.
//
// Trabaja con cuaterniones, así que no tiene el problema de los ángulos de Euler a 90°
// (el robot en la pared). El rumbo (giro alrededor de la vertical) no se puede corregir sin
// magnetómetro y se desvía: los nodos de ROS solo usan inclinación, cabeceo y alabeo.
#pragma once

#include <math.h>

class FiltroOrientacion {
 public:
  // kp: qué tan rápido corrige hacia el acelerómetro (más alto = más confía en el acelerómetro)
  explicit FiltroOrientacion(float kp = 1.0f) : kp_(kp) {}

  // Arranca con la orientación que da el acelerómetro (robot quieto).
  void iniciar(float ax, float ay, float az) {
    const float roll = atan2f(ay, az);
    const float pitch = atan2f(-ax, sqrtf(ay * ay + az * az));
    const float cr = cosf(roll / 2), sr = sinf(roll / 2), cp = cosf(pitch / 2), sp = sinf(pitch / 2);
    w_ = cr * cp;
    x_ = sr * cp;
    y_ = cr * sp;
    z_ = -sr * sp;
    iniciado_ = true;
  }

  // a en m/s² (cualquier unidad sirve, se normaliza), g en rad/s, dt en segundos.
  void actualizar(float ax, float ay, float az, float gx, float gy, float gz, float dt) {
    if (!iniciado_) {
      iniciar(ax, ay, az);
      return;
    }
    const float norma = sqrtf(ax * ax + ay * ay + az * az);
    if (norma > 1e-3f) {
      ax /= norma;
      ay /= norma;
      az /= norma;
      // Gravedad esperada según la orientación actual
      const float vx = 2 * (x_ * z_ - w_ * y_);
      const float vy = 2 * (w_ * x_ + y_ * z_);
      const float vz = w_ * w_ - x_ * x_ - y_ * y_ + z_ * z_;
      // Error = producto cruz entre la gravedad medida y la esperada
      gx += kp_ * (ay * vz - az * vy);
      gy += kp_ * (az * vx - ax * vz);
      gz += kp_ * (ax * vy - ay * vx);
    }
    // Integrar q' = 0.5 * q ⊗ (0, g)
    const float h = 0.5f * dt;
    const float w = w_ + (-x_ * gx - y_ * gy - z_ * gz) * h;
    const float x = x_ + (w_ * gx + y_ * gz - z_ * gy) * h;
    const float y = y_ + (w_ * gy - x_ * gz + z_ * gx) * h;
    const float z = z_ + (w_ * gz + x_ * gy - y_ * gx) * h;
    const float n = sqrtf(w * w + x * x + y * y + z * z);
    w_ = w / n;
    x_ = x / n;
    y_ = y / n;
    z_ = z / n;
  }

  // Ángulo entre el eje z del sensor y la vertical, en grados (0 = plano, 90 = pared).
  float inclinacion() const {
    float c = 1.0f - 2.0f * (x_ * x_ + y_ * y_);
    c = c > 1.0f ? 1.0f : (c < -1.0f ? -1.0f : c);
    return acosf(c) * 57.2957795f;
  }

  float w() const { return w_; }
  float x() const { return x_; }
  float y() const { return y_; }
  float z() const { return z_; }
  bool iniciado() const { return iniciado_; }

 private:
  float kp_;
  float w_ = 1, x_ = 0, y_ = 0, z_ = 0;
  bool iniciado_ = false;
};
