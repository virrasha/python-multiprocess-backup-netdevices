import sys
import paramiko
import time
import subprocess
from save_words import save_and_send_words 

script_name,hostname,ip,login,model,tag,tftp_ip,log_dir,key_file = sys.argv

def read_until (channel,end_str,max_timeout,step_timeout):
    data = ""
    while max_timeout>0:
        if channel.recv_ready():
            str2 = channel.recv(2).decode()
            while str2 != "":
                data += str2
                str2 = channel.recv(2).decode()
                if end_str in data:
                    return f"FIND SUCCESS ({end_str})\n"
        time.sleep(step_timeout)
        max_timeout-=step_timeout
    return f"TIMEOUT READING FROM SSH CHANNEL, FIND FAIL ({end_str})\ndata is\n{data}"

#Not only AR, SW5700 Series too
#Разобраться почему invoke shell работает, а просто запуск ssh как у циски - не работает (говорит - не терминал)
def huawei_AR_backup(hostname,ip,login,model):
    with open(log_dir+hostname+".log",mode="w",encoding="utf-8") as logfile:
        logfile.write("START\n")
        try:
            with paramiko.SSHClient() as ssh:
                end_of_save=save_and_send_words[model][0]
                end_of_send=save_and_send_words[model][1]
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) #разрешать ранее неизвестные ключики
                ssh.connect(hostname=ip,username=login,key_filename=key_file,disabled_algorithms=dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256","ecdsa-sha2-nistp521"]))
                logfile.write("ssh connected successfully\n")
                cli=ssh.invoke_shell()
                if (model == "SW6730"):
                    cli.send(f'save {hostname}.cfg\ny\n') 
                else:
                    cli.send(f'save {hostname}.cfg\ny\ny\n')  
                logfile.write(read_until(cli,end_of_save,30.0,0.3))
                cli.send(f'tftp {tftp_ip} put {hostname}.cfg {hostname}.cfg\n')
                logfile.write(read_until(cli,end_of_send,30.0,0.3))
        except paramiko.BadHostKeyException:
            logfile.write("BadHostKeyException\n")
            return 1
        except paramiko.AuthenticationException:
            logfile.write("AuthenticationException\n")
            return 2
        except paramiko.SSHException:
            logfile.write("SSHException\n")
            return 3
    return 0

def huawei_S6730_backup(hostname,ip,login,model):
    return 0

def cisco_2960_backup(hostname,ip,login,model):
    with open(log_dir+hostname+".log",mode="w",encoding="utf-8") as logfile:
        logfile.write("START\n")
        args = ["/usr/bin/ssh", f"{login}@{ip}", "-oKexAlgorithms=+diffie-hellman-group1-sha1", "-oHostKeyAlgorithms=+ssh-rsa", "-oStrictHostKeyChecking=no","-c", "aes256-cbc,aes256-ctr"]
        
        try:
            with subprocess.Popen(args,stdout=subprocess.PIPE, stderr=subprocess.STDOUT,stdin=subprocess.PIPE,text=True) as cisco_proc:
                logfile.write("ssh open process successfully\n")
                output = cisco_proc.communicate(input=f'copy run tftp://{tftp_ip}/{hostname}.cfg\n\n\n',timeout=30)[0]
                logfile.write(output)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as err:
            logfile.write(f"error {err}\n")
            return 1
    return 0

def cisco_sf300_backup(hostname,ip,login,model):
    with open(log_dir+hostname+".log",mode="w",encoding="utf-8") as logfile:
        logfile.write("START\n")
        try:
            with paramiko.SSHClient() as ssh:
                logfile.write("ssh open process successfully\n")
                end_of_send=save_and_send_words[model][1]
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(hostname=ip,username=login,key_filename=key_file,disabled_algorithms=dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256"]))
                cli=ssh.invoke_shell()
                cli.send(f'en\ncopy run tftp://{tftp_ip}/{hostname}.cfg\n')
                logfile.write(read_until(cli,end_of_send,30.0,0.3))
        except paramiko.BadHostKeyException:
            logfile.write("BadHostKeyException\n")
            return 1
        except paramiko.AuthenticationException:
            logfile.write("AuthenticationException\n")
            return 2
        except paramiko.SSHException:
            logfile.write("SSHException\n")

def maipu_backup (hostname,ip,login,model):
    with open(log_dir+hostname+".log",mode="w",encoding="utf-8") as logfile:
        logfile.write("START\n")
        try:
            with paramiko.SSHClient() as ssh:
                end_of_send=save_and_send_words[model][1]
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) #разрешать ранее неизвестные ключики
                ssh.connect(hostname=ip,username=login,key_filename=key_file,disabled_algorithms=dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256"]))
                logfile.write("ssh connected successfully\n")
                cli=ssh.invoke_shell()
                cli.send(f'copy run tftp {tftp_ip} {hostname}.cfg\n')
                logfile.write(read_until(cli,end_of_send,30.0,0.3))
        except paramiko.BadHostKeyException:
            logfile.write("BadHostKeyException\n")
            return 1
        except paramiko.AuthenticationException:
            logfile.write("AuthenticationException\n")
            return 2
        except paramiko.SSHException:
            logfile.write("SSHException\n")
            return 3
    return 0
        
if tag == "huawei" and model in ("AR6120","AR6140","SW5735","AR6280","SW6730"):
    huawei_AR_backup(hostname,ip,login,model)
elif tag == "cisco" and model in ("SW2960","SF300"):
    if model == "SW2960":
        cisco_2960_backup(hostname,ip,login,model)
    elif model == "SF300":
        cisco_sf300_backup(hostname,ip,login,model)
elif tag == "maipu":
    maipu_backup(hostname,ip,login,model)