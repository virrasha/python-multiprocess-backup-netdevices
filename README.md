# python-multiprocess-backup-netdevices
Script for parallel backup network devices.
supported: huawei routers ar6120, ar6140, ar6280, huawei switches s5735, 6730. Cisco old 2960, sf300. Maipu switches s3330.
Start is backup_multiprocess.py. 
For each device will start process one_backup.py.
You need sqlite database for devices. Name database is netdevices. Name table is netdev. Columns are text: hostname,ip,login,pass,tag,model.
Tag is: huawei, cisco, maipu. 
Model is: SW5735, AR6120, AR6140, AR6280, SW6730, SW2960, SF300, SW3330
insert is like:
insert into netdev (hostname,ip,login,pass,tag,model) values ( 'vol-s5735-24-1', '10.10.10.1','backupuser','','huawei','SW5735');

You don't need password in database if your devices support connection by ssh keys.

You also need file save_words.py to check if backup is success.
