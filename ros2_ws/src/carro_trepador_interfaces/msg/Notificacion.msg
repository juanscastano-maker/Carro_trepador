# Notificación del supervisor para el operador (tópico /gui/notifications).
# Ver docs/arquitectura/Arquitectura_Carro_trepador_v4.docx, sección 7.

uint8 INFO=0
uint8 AVISO=1
uint8 ALERTA=2

builtin_interfaces/Time stamp   # cuándo ocurrió
uint8 nivel                     # INFO, AVISO o ALERTA
string origen                   # supervisor, firmware, bateria, imu_delantera, ...
string codigo                   # identificador corto, p. ej. ESTADO_PARED, DRV_FALLA
string texto                    # mensaje para el operador
