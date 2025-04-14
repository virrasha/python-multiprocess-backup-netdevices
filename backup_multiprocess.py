import sqlite3
import time
import subprocess
from datetime import datetime
from save_words import save_and_send_words 
import os.path
import os
import glob
import paramiko

tftp_ip = "10.10.10.10"
log_dir = "/config/tmpfiles/python_logs/"
key_file = "/root/.ssh/id_rsa"
key_git = "/root/.ssh/rsa_2048"
tftp_dir="/config/huawei/tftp"
max_processes = 20 #how much parallell backups will start
max_timeout_to_process = 300 #in seconds
retry_interval = 3 #in seconds
logfiles = []
retry_timeout = 600 #in seconds
result_file_log = "/config/tmpfiles/python_logs/result.txt"

#mail values
mail_to = "NetworkInfo@mydomain.ru"
mail_from = "ScriptInfo@mydomain.ru"
mail_auth_pass = "**********"
mail_server = "s00-0000-mail01.mydomain.ru"

#generate list of devices from database
connect_netdev = sqlite3.connect('/config/database/netdevices.db')
cursor_netdev = connect_netdev.cursor()
devicesRequest = cursor_netdev.execute("SELECT hostname,ip,login,model,tag from netdev;") #return tuple or None
connect_netdev.close
devices_first_backup = devicesRequest.fetchall()

def retry_func(retry_list):
    retry_devices=[]
    for dev in retry_list:
        OneDevicesRequest = cursor_netdev.execute(f'SELECT hostname,ip,login,model,tag from netdev where hostname is "{dev["hostname"]}";')
        retry_devices.append(OneDevicesRequest.fetchone())
    return retry_devices

def multiprocess_run(devices):
    running_proc_count = 0
    procs_with_time = {} #dict where key is process object and value is timestart
    
    def try_start_backup():
        nonlocal running_proc_count
        nonlocal procs_with_time
        if running_proc_count >= max_processes: #no more slots
            return
        if len(devices) == 0: #no more devices
            return
        device = devices.pop()
        hostname,ip,login,model,tag = device  
        logfiles.append(f'{hostname}.log {model}')
        args=["/bin/python3","/config/python_repa_clone/python_scripts/one_backup.py",hostname,ip,login,model,tag,tftp_ip,log_dir,key_file]
        process_start = subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        #формируем список процессов с указанием времени их запуска
        procs_with_time [process_start] = time.time()
        running_proc_count += 1
        try_start_backup()

    def check_end_of_process():
        nonlocal running_proc_count
        procs_clone = procs_with_time.copy()
        for proc in procs_clone.keys():
            if (proc.poll() != None): #process ends successfull before timeout
                running_proc_count -= 1
                procs_with_time.pop(proc)
            if ((time.time() - procs_clone[proc]) > max_timeout_to_process): #process is runing more than max timeout
                running_proc_count -= 1
                procs_with_time.pop(proc)
                proc.kill()

    try_start_backup() #starting

    while (running_proc_count != 0):
        time.sleep(retry_interval)
        check_end_of_process()
        try_start_backup()

def analyse_result(retry):
    #results: 
    #sortedlist = sorted(my_list , key=lambda elem: "%02d %s" % (elem['age'], elem['name']))
    #results: SUCCESS, ERROR, RETRY, NOFUNC
    result_list = [] #[{'hostname':'mai-ar6120-1.log', 'result': 'SUCCESS', 'string': ''},{}]
    #block to test analyticks without backup
    #for device in devices:
    #    hostname,ip,login,model,tag = device
    #    logfiles.append(f"{hostname}.log {model}")
    #end of block to test analyticks without backup
    with open(result_file_log,mode="a",encoding="utf-8") as log_res:
        log_res.write(datetime.now().strftime("ANALYSE NETWORK BACKUPS %Y-%m-%d %H:%M:%S \n"))
        if(retry):
            log_res.write("!!!RETRY SECOND BACKUP!!!\n")
        for logfile_m in logfiles:
            logfile,model=logfile_m.split()
            line_to_log="NEED RETRY"
            hostname=logfile.split('.')[0]
            result="RETRY"
            if (not os.path.isfile(log_dir+logfile)):
                line_to_log= "---NOT SUCH FILE (no function to make backup)---"
                result="NOFUNC"
                result_list.append({'hostname': hostname, 'result': result, 'string': line_to_log})
                continue
            with open(log_dir+logfile,mode="r",encoding="utf-8") as logfl:
                for line in logfl:
                    if (save_and_send_words[model][1] in line):
                        line_to_log="BACKUP SUCCESS"
                        result = "SUCCESS"
                        result_list.append({'hostname': hostname, 'result': result, 'string': line_to_log})
                        break
                    for word in save_and_send_words['errors']:
                        if word in line:
                            line_to_log="ERRORS FIND" +f"\n   {line}" 
                            result = "ERROR"
                            result_list.append({'hostname': hostname, 'result': result, 'string': line_to_log})
            if (line_to_log == "NEED RETRY"):
                result_list.append({'hostname': hostname, 'result': result, 'string': line_to_log})
        sortedlist = sorted(result_list , key=lambda elem: "%s %s" % (elem['result'], elem['hostname']))
        for element in sortedlist:
            log_res.write(f"{element['result']} для {element['hostname']} подробности: {element['string']}\r")
    args = f"swaks -tls -a \
        --to {mail_to} \
        --from {mail_from} \
        --server {mail_server} \
        --auth-user {mail_from}  \
        --auth-password {mail_auth_pass} \
        --h-Subject \"ПИТОНЯЧИЙ отчет по бэкапам сетевого оборудования\" \
        --attach-body {result_file_log}"
    #Без авторизации:
    #args=f"/usr/bin/mail {mail_info} < {result_file_log} -s \"ПИТОНЯЧИЙ отчет по бэкапам сетевого оборудования\""
    
    subprocess.Popen(args,shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    retry_list = filter(lambda device: device['result'] == 'RETRY', result_list)
    return retry_list     

def commit_it():
    #Внимание, с правами на репу!

    args=f"/usr/bin/git -C {tftp_dir} add ."
    pr = subprocess.Popen(args,shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    date_n=datetime.now().strftime("\"PYTHON BACKUP COMMIT %Y-%m-%d %H:%M:%S\"")
    pr.wait()
    args=f"/usr/bin/git -C {tftp_dir} commit -m {date_n}"
    pr = subprocess.Popen(args,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = pr.communicate()
    with open(result_file_log,mode="w",encoding="utf-8") as log_res:
        log_res.write("COMMIT STATUS\n")
        log_res.write(out.decode('utf-8'))
        log_res.write(err.decode('utf-8'))
        log_res.write("\n")
        pr.wait()
        args=f"eval \"$(ssh-agent -s)\";ssh-add {key_git};/usr/bin/git -C {tftp_dir} push"
        pr = subprocess.Popen(args,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out,err = pr.communicate()
        log_res.write(out.decode('utf-8'))
        log_res.write(err.decode('utf-8'))
        log_res.write("\n")
        pr.wait(timeout=90)
    
    return


def delete_logs():
    files = glob.glob(f"{log_dir}*.log")
    for f in files:
        os.remove(f)
    return



#START IS HERE

delete_logs()
multiprocess_run(devices_first_backup)#starting carousel of processes
commit_it()#git commit and push
retry_list=list(analyse_result(retry=0))#analyse and send result in e-mail

#RETRY BACKUP for fail jobs
retry_devices = retry_func(retry_list)
time.sleep(retry_timeout)
logfiles = []
result_file_log = "/config/tmpfiles/python_logs/result_retry.txt"
log_dir = "/config/tmpfiles/python_logs/retry/"
max_timeout_to_process += 120
delete_logs()
multiprocess_run(retry_devices)#starting carousel of processes
commit_it()#git commit and push
analyse_result(retry=1)
