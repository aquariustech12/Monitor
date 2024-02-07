import hashlib
import os
import psutil
import smtplib
import schedule
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

sitios_web_respaldo = "/home/julian/sitios_web_respaldo/"
gitea_respaldo = "/home/julian/gitea_respaldo/"

# Crear directorios de respaldo si no existen
if not os.path.exists(sitios_web_respaldo):
    os.makedirs(sitios_web_respaldo)

if not os.path.exists(gitea_respaldo):
    os.makedirs(gitea_respaldo)

# Configurar el servidor de correo electrónico
mail_server = "smtp.gmail.com"
mail_server_port = 587
from_addr = "julianlugo7402@gmail.com"
to_addr = "marketingconsultantsmx@gmail.com"
password = "aprtkmdrqmqimbve"

def monitor_performance():
    # Obtener el uso de la CPU
    cpu_usage = psutil.cpu_percent(interval=1)

    # Obtener el uso de la memoria
    memory_info = psutil.virtual_memory()
    memory_total = memory_info.total
    memory_used = memory_info.used
    memory_percentaje = memory_info.percent

    # Obtener el uso del disco
    disk_info = psutil.disk_usage('/')
    disk_total = disk_info.total
    disk_used = disk_info.used
    disk_percentaje = disk_info.percent

    print(f"Uso de la CPU: {cpu_usage}%")
    print(f"Memoria total: {memory_total} bytes")
    print(f"Memoria utilizada: {memory_used} bytes")
    print(f"Uso de la memoria: {memory_percentaje}%")
    print(f"Disco total: {disk_total} bytes")
    print(f"Disco utilizado: {disk_used} bytes")
    print(f"Uso del disco: {disk_percentaje}%")

    # Crear el mensaje de correo electrónico
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = "Reporte de rendimiento del servidor"
    body = f"Uso de la CPU: {cpu_usage}%\nUso de la memoria: {memory_percentaje}%\nUso del disco: {disk_percentaje}%"
    msg.attach(MIMEText(body, "plain"))

    # Enviar el correo electrónico
    server = smtplib.SMTP(mail_server, mail_server_port)
    server.starttls()
    server.login(from_addr, password)
    text = msg.as_string()
    server.sendmail(from_addr, to_addr, text)
    server.quit()

def calculate_md5(file_path):
    with open(file_path, "rb") as f:
        file_hash = hashlib.md5()
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return file_hash.hexdigest()

# Monitorear los registros del sistema
def monitor_logs():
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path="/var/log", recursive=True)
    observer.start()

    # Observar durante 10 segundos
    start_time = time.time()
    try:
        while time.time() - start_time < 10:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Tareas de mantenimiento a ejecutar una vez por semana, los lunes a las 12 pm
def maintenance_tasks():
    print("Ejecutando tareas de mantenimiento...")

    # 1. Actualización del Sistema
    os.system("sudo apt update && sudo apt upgrade -y")

    # 2. Limpieza de Archivos Temporales
    os.system("sudo rm -rf /tmp/*")
    os.system("sudo apt autoclean && sudo apt autoremove -y")

    # 3. Respaldo de Sitios Web y Aplicaciones
    os.system(f"rsync -a --delete /var/www/html/ {sitios_web_respaldo}")

    # 4. Respaldo de Configuración y Datos de Gitea
    os.system(f"rsync -a --delete /var/lib/gitea/ {gitea_respaldo}")

    # 5. Revisión de Logs
    os.system("sudo find /var/log -type f -name '*.gz' -exec rm {} +")

    # 6. Escaneo de Malware (ejemplo con ClamAV)
    os.system("sudo clamscan -r /")

    # 7. Reinicio del Servidor
    # Comenta la siguiente línea si no deseas reiniciar el servidor automáticamente
    #os.system("sudo reboot")

if __name__ == "__main__":
    # Programar las tareas de mantenimiento cada lunes a las 12 pm
    schedule.every().monday.at("12:00").do(maintenance_tasks)

    # Ejecutar las tareas de mantenimiento de inmediato
    maintenance_tasks()

    # Ejecutar el monitoreo de rendimiento y registros
    while True:
        schedule.run_pending()
        monitor_performance()
        monitor_logs()
        time.sleep(1)
