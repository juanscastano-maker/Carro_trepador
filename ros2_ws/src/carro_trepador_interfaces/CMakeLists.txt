cmake_minimum_required(VERSION 3.8)
project(carro_trepador_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

# Mensajes propios del proyecto
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Notificacion.msg"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
