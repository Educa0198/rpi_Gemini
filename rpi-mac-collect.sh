#!/bin/bash
dt=$(date '+%Y-%m-%dT%H:%M:%S');
cd /app/rpi/code;
echo "RPI MAC Collect script started at $dt"
# source ./.venv/bin/activate;
pip3 install -r requirements.txt
sleep 1;
sudo python ./mac_tcp.py > mac-wifi.log
# nohup python mac_bluetooth.py >> mac-wifi.log &
sleep 2;
# echo "RPI mac script finished successfully. Check mac-wifi.log file for details."
dt=$(date '+%Y-%m-%dT%H:%M:%S');
echo "RPI mac wifi collect script finished at $dt. You can watch mac-wifi.log file for details."
sleep 2;
exit 0;
