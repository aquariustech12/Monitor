import psutil

# Obtener el uso de la CPU
cpu_usage = psutil.cpu_percent(interval=1)

# Obtener el uso de la memoria
memory_info = psutil.virtual_memory()
memory_total = memory_info.total
memory_used = memory_info.used
memory_percentage = memory_info.percent

# Obtener el uso del disco
disk_info = psutil.disk_usage('/')
disk_total = disk_info.total
disk_used = disk_info.used
disk_percentage = disk_info.percent

print(f"Uso de la CPU: {cpu_usage}%")
print(f"Memoria total: {memory_total} bytes")
print(f"Memoria utilizada: {memory_used} bytes")
print(f"Uso de la memoria: {memory_percentage}%")
print(f"Disco total: {disk_total} bytes")
print(f"Disco utilizado: {disk_used} bytes")
print(f"Uso del disco: {disk_percentage}%")