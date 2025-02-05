#!/bin/bash
# ./run_import.sh us_ofac_sdn

# Función para imprimir la hora y el mensaje
log_with_time() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Verificar si se proporcionó un argumento
if [ $# -eq 0 ]; then
  log_with_time "Por favor, proporciona el nombre del archivo como argumento."
  exit 1
fi

# Asignar el argumento a una variable
archivo=$1

# Usar un "switch" (case) para seleccionar la ruta basada en el archivo
case $archivo in
  "us_ofac_sdn")
    dataset_path="datasets/us/ofac/us_ofac_sdn.yml"
    dataset_path_csv="data/datasets/us_ofac_sdn/targets.simple.csv"
    ;;
  "co_funcion_publica")
    dataset_path="datasets/co/funcion_publica/co_funcion_publica.yml"
    dataset_path_csv="data/datasets/co_funcion_publica/targets.simple.csv"
    ;;
   "interpol_red_notices")
    dataset_path="datasets/_global/interpol/interpol_red_notices.yml"
    dataset_path_csv="data/datasets/interpol_red_notices/targets.simple.csv"
    ;;
   "de_abgeordnetenwatch")
    dataset_path="datasets/de/abgeordnetenwatch/de_abgeordnetenwatch.yml"
    dataset_path_csv="data/datasets/de_abgeordnetenwatch/targets.simple.csv"
    ;;
  *)
    log_with_time "Archivo no reconocido: $archivo"
    exit 1
    ;;
esac

# Ejecutar el comando Docker para limpiar los datos
log_with_time "Ejecutando el comando Docker para limpiar los datos..."
docker compose run --rm app zavod clear $dataset_path
if [ $? -ne 0 ]; then
  log_with_time "Error en el comando Docker 'clear'. Abortando."
  exit 1
fi

# Ejecutar el comando Docker para hacer crawling
log_with_time "Ejecutando el comando Docker para hacer crawling..."
docker compose run --rm app zavod crawl $dataset_path
if [ $? -ne 0 ]; then
  log_with_time "Error en el comando Docker 'crawl'. Abortando."
  exit 1
fi

# Ejecutar el comando Docker para exportar los datos
log_with_time "Ejecutando el comando Docker para exportar los datos..."
docker compose run --rm app zavod export $dataset_path
if [ $? -ne 0 ]; then
  log_with_time "Error en el comando Docker 'export'. Abortando."
  exit 1
fi

# Si los comandos Docker fueron exitosos, proceder a ejecutar el comando Laravel
log_with_time "Comandos Docker ejecutados con éxito. Ahora ejecutando el comando Laravel para importar datos..."

# Navegar al directorio del proyecto Laravel
cd /c/xampp/htdocs/sanctions360

# Ejecutar el comando Laravel
php artisan import:csv /c/xampp/htdocs/opensanctions/$dataset_path_csv
if [ $? -ne 0 ]; then
  log_with_time "Error en el comando Laravel. Abortando."
  exit 1
fi

log_with_time "Proceso completado exitosamente."
