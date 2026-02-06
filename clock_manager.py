import subprocess
from datetime import datetime
import uuid

def timestampNow():
  result = subprocess.run(
    ["sudo", "hwclock", "-r"], 
    capture_output=True, text=True, check=True
  )
  output = result.stdout.strip()

  # Tenta vários formatos possíveis de saída do hwclock
  formatos = [
    "%Y-%m-%d %H:%M:%S.%f%z",   # formato ISO com timezone
    "%Y-%m-%d %H:%M:%S%z",      # formato ISO sem microsegundos
    "%a %d %b %Y %I:%M:%S %p %z",  # formato estilo "Mon 15 Sep 2025 04:35:10 PM -03"
  ]

  for fmt in formatos:
    try:
      return datetime.strptime(output, fmt)
    except ValueError:
      continue

  raise ValueError(f"Formato inesperado do hwclock: {output}")

def getFormattedTimestamp(format: str = "%Y-%m-%d %H:%M:%S", includeUUId=True) -> str:
  """Return current timestamp as 'YYYY-MM-DD HH:MM:SS'."""
  try:
    return timestampNow().strftime(format)
  except:
    return f'clock-not-found-{uuid.uuid4()}'