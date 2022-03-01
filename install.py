import argparse
import logging
import os
import random
import shutil
import string
import subprocess
from pathlib import Path
import time

import yaml

logging.basicConfig(filename='install.log', level=logging.DEBUG)


def log_debug(text):
    logging.debug(text)


def show_message(text, title=False):
    if title:
        text = f'\n####### {text} #######\n'
    log_debug(text)
    print(text)


def confirm_action(question):
    valid = {'yes': True, 'ye': True, 'y': True, 'no': False, 'n': False}
    answer = input(question + ' [Y/n]: ').strip().lower()
    if answer == '':
        return False
    elif answer in valid:
        return valid[answer]
    else:
        show_message('Please try again and answer correctly. For instance you can type \'yes\' or \'y\'')
        return confirm_action(question)


def generate_password(length=16):
    return ''.join(
        random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(length))


def confirm_value(value, text):
    return input('Confirm ' + text).strip() == value


def run_shell_command(command: list) -> str:
    log_debug('run_shell_command')
    return subprocess.run(command, stdout=subprocess.PIPE).stdout.decode('utf-8')


def install_docker():
    log_debug('install_docker')
    show_message('Install docker and docker-compose')
    out = run_shell_command(['apt', 'install', 'docker', 'docker-compose', '-y'])
    log_debug(out)


def install_certbot():
    log_debug('install_certbot')
    show_message('Install certbot')
    out = run_shell_command(['apt', 'install', 'certbot', '-y'])
    log_debug(out)
    out = run_shell_command(['apt', 'install', 'python3-certbot-nginx', '-y'])
    log_debug(out)


def remove_sql_data():
    log_debug('remove sql dir')
    show_message('Remove existing sql data')
    databases = [
        '/opt/postgresql-synapse',
        '/opt/postgresql-coturn',
    ]
    for d in databases:
        if os.path.isdir(d):
            shutil.rmtree(d)

def remove_backend_data():
    log_debug('remove data')
    show_message('Remove backend data')
    backend_data = [
        'data',
        'install.log',
        'configs/coturn/turnserver.conf',
        'configs/env/common.env',
        'configs/env/coturn.env',
        'configs/env/jitsi.env',
        'configs/env/matrix.env',
        'configs/jitsi',
        'configs/postgres',
        'configs/nginx/nginx.conf',
        'host.lock',
        '/etc/nginx/nginx.conf',
        '/etc/sites-available/default',
        '/etc/sites-enabled/default',
        '/etc/nginx/conf.d/nginx.conf'
    ]
    
    for data_path in backend_data:
        if os.path.isdir(data_path):
            show_message(f'Removing {data_path}')
            shutil.rmtree(data_path)
        elif os.path.isfile(data_path):
            show_message(f'Removing {data_path}')
            os.remove(data_path)


def get_confirmed_inputed_value(text):
    value = input(text).strip()
    if confirm_value(value, text):
        return value
    print('Confirm value was wrong, please retype value')
    return get_confirmed_inputed_value(text)


def create_synapse_config():
    log_debug('create_synapse_config')
    run_shell_command(['docker-compose', '-f', 'docker-compose.matrix.yml', 'run', '--rm', 'synapse', 'generate'])


def get_env_data_as_dict(path: str) -> dict:
    with open(path, 'r') as f:
        return dict(tuple(line.replace('\n', '').split('=')) for line in f.readlines() if
                    not (line.startswith('#') or len(line.strip()) == 0))


class MatrixBackendStack:

    def __init__(self):
        self.synapse_db_password = generate_password()
        self.turn_shared_secret = generate_password(64)
        self.coturn_db_password = generate_password(16)
        self.install_path = Path(__file__).parent.resolve()
        self.base_docker_command = ['docker-compose',
                        '-f', 'docker-compose.jitsi.yml',
                        '-f', 'docker-compose.matrix.yml']
        self.subdomains = ['matrix', 'meet']
        self.steps = 25
        self.current_step = 0

    def init_domain_and_email(self, domain, email):
        self.host = domain
        self.email = email

    def write_progress(self, text, complete = False):
        self.current_step+=1
        with open('data/install_progress.json', 'w+') as file:
            file.write(f'{{"progress":{int(self.current_step/self.steps*100)},"text":"{text}{"..." if not complete else ""}","complete":{"true" if complete else "false"},"domain":"{self.host}","email":"{self.email}"}}')

    def stop_existing_containers(self):
        log_debug('stop running containers')
        show_message('Stop running containers if exists')
        self.write_progress("Stop running containers if exists")
        out = run_shell_command(self.base_docker_command + ['down'])
        log_debug(out)

    def run_docker_compose(self):
        log_debug('run_docker_compose')
        self.write_progress("Run docker compose...")
        run_shell_command(self.base_docker_command + ['up', '-d'])

    def ask_questions(self):
        log_debug('ask_questions')
        show_message('Please enter next mandatory information:')
        self.write_progress("Domain and Email data assignment")
        if self.host is None:
            self.host = get_confirmed_inputed_value('Domain for services: ')
        if self.email is None:
            self.email = get_confirmed_inputed_value('Email: ')

    def start_certbot(self):
        log_debug('start_certbot')
        if (os.path.isfile(f'/etc/letsencrypt/live/api.{self.host}/fullchain.pem')):
            run_shell_command(['certbot', 'renew'])
            show_message('Certificate already exists. Skipping...')
            self.write_progress('Certificate exists. Skipping')
            return
        show_message('Start getting SSL certificate')
        self.write_progress('Start getting SSL certificate')
        out = run_shell_command(['certbot', '--nginx', '-n', '--agree-tos', '--email', self.email, '-d', f'api.{self.host}', '-d', f'matrix.{self.host}', '-d', f'meet.{self.host}'])
        log_debug(out)
        with open('host.lock', 'w') as file:
            file.write(f'{self.host}')

    def delete_certs(self):
        log_debug('delete_certs')
        show_message('Deleting certs')
        out = run_shell_command(['service', 'nginx', 'restart'])
        log_debug(out)
        out = run_shell_command(['certbot', 'delete', '--cert-name', f'api.{self.host}'])
        log_debug(out)

        

    def write_jitsi_env(self):
        self.write_progress('Writting Jitsi .env file')
        config = get_env_data_as_dict('configs/env/jitsi_template.env')
        config['JICOFO_AUTH_PASSWORD'] = generate_password()
        config['JVB_AUTH_PASSWORD'] = generate_password()
        config['JIGASI_XMPP_PASSWORD'] = generate_password()
        config['JIBRI_RECORDER_PASSWORD'] = generate_password()
        config['JIBRI_XMPP_PASSWORD'] = generate_password()
        config['PUBLIC_URL'] = f'https://meet.{self.host}'
        config['LETSENCRYPT_DOMAIN'] = f'meet.{self.host}'
        config['LETSENCRYPT_EMAIL'] = self.email
        config['ENABLE_LETSENCRYPT'] = '0'

        with open('configs/env/jitsi.env', 'w+') as file:
            for (k, v) in config.items():
                file.write(f'{k}={v}\n')

    def write_matrix_env(self):
        log_debug('write_matrix_env')
        self.write_progress('Writting Matrix .env file')
        with open('configs/env/matrix.env', 'w+') as file:
            # Postgres
            file.write(f'POSTGRES_PASSWORD={self.synapse_db_password}\n')
            file.write(f'POSTGRES_USER=synapse\n')
            file.write(f'POSTGRES_DB=synapse\n')
            file.write(f"POSTGRES_INITDB_ARGS=--encoding='UTF8' --lc-collate='C' --lc-ctype='C'\n")

            # Synapse
            file.write(f'VIRTUAL_HOST=matrix.{self.host}\n')
            file.write(f'VIRTUAL_PORT=8008\n')
            file.write(f'LETSENCRYPT_HOST=matrix.{self.host}\n')
            file.write(f'SYNAPSE_SERVER_NAME=matrix.{self.host}\n')
            file.write(f'SYNAPSE_REPORT_STATS=yes\n')

    def write_common_env(self):
        log_debug('write_common_env')
        self.write_progress('Writting common .env file')
        with open('configs/env/common.env', 'w+') as file:
            # Services
            jwt_secret = generate_password(64)
            file.write(f'JWT_SECRET={jwt_secret}\n')
            file.write(f'API_SERVER_DOMAIN=https://api.{self.host}/v0\n')
            file.write(f'EUREKA_HOST=api-registry\n')

    def write_coturn_env(self):
        self.write_progress('Writting Coturn .env file')
        with open('configs/env/coturn.env', 'w+') as file:
            file.write(f'POSTGRES_DB=coturn\n')
            file.write(f'POSTGRES_USER=coturn\n')
            file.write(f'POSTGRES_PASSWORD={self.coturn_db_password}\n')
            file.write(f"POSTGRES_INITDB_ARGS=--encoding='UTF8' --lc-collate='C' --lc-ctype='C'\n")

            file.write(f'INSTALL_PREFIX=/usr/local\n')
            file.write(f'TURNSERVER_GROUP=turnserver\n')
            file.write(f'TURNSERVER_USER=turnserver\n')

    ################################# config #################################

    def fix_synapse_config(self):
        log_debug('fix_synapse_config')
        self.write_progress('Synapse config file parameter substitution')
        with open('data/synapse/homeserver.yaml', 'r') as file:
            try:
                config = yaml.safe_load(file)
            except yaml.YAMLError as exc:
                log_debug(exc)

        config['database']['name'] = 'psycopg2'
        config['database']['args'] = {
            'user': 'synapse',
            'password': self.synapse_db_password,
            'host': 'localhost',
            'database': 'synapse',
            'cp_min': 5,
            'cp_max': 15,
        }

        config['turn_uris'] = [
            f'turns:matrix.{self.host}?transport=udp',
            f'turns:matrix.{self.host}?transport=tcp',
            f'turn:matrix.{self.host}?transport=udp',
            f'turn:matrix.{self.host}?transport=tcp'
        ]
        config['enable_registration'] = 'true'
        config['turn_shared_secret'] = self.turn_shared_secret
        config['ip_range_whitelist'] = ['127.0.0.1/8', '0.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
                                        '100.64.0.0/10', '169.254.0.0/16']
        config['public_baseurl'] = f'https://matrix.{self.host}'

        self.write_progress('Create Synapse homeserver.yaml file')
        with open('data/synapse/homeserver.yaml', 'w+') as file:
            file.write(yaml.dump(config))

    def fix_coturn_config(self):
        self.write_progress('Coturn config file parameter substitution')
        with open('configs/coturn/turnserver.conf', 'w+') as file:
            file.write('listening-port=3478\n')
            file.write('tls-listening-port=5349\n')
            file.write('external-ip=\n')
            file.write('min-port=49152\n')
            file.write('max-port=65535\n')
            file.write('verbose\n')
            file.write('fingerprint\n')
            file.write('lt-cred-mech\n')
            file.write('use-auth-secret\n')

            file.write(f'static-auth-secret={self.turn_shared_secret}\n')
            file.write(
                f'psql-userdb="host=localhost port=15432 dbname=coturn user=coturn password={self.coturn_db_password} connect_timeout=60"\n')
            file.write(f'realm=matrix.{self.host}\n')

            file.write('cert=/etc/ssl/certs/cert.pem\n')
            file.write('pkey=/etc/ssl/private/privkey.pem\n')
            file.write('syslog\n')
            file.write('cli-ip=127.0.0.1\n')
            file.write('cli-port=5766\n')
            file.write(f'cli-password={generate_password()}\n')

    def fix_sygnal_config(self):
        log_debug('fix_sygnal_config')
        self.write_progress('Sygnal config file parameter substitution')
        with open('configs/sygnal/sygnal.yaml', 'r') as file:
            try:
                config = yaml.safe_load(file)
            except yaml.YAMLError as exc:
                log_debug(exc)

        # TODO replace api_key with env variable
        config['apps']['im.vector.app.android:'] = {
            'type': 'gcm',
            'api_key': '',
        }
        self.write_progress('Create sygnal.yaml file')
        with open('configs/sygnal/sygnal.yaml', 'w+') as file:
            file.write(yaml.dump(config))

    def fix_nginx_config(self):
        self.write_progress('Create nginx config file')
        with open('configs/nginx/nginx-conf.template', 'r') as file:
            config = file.read()

        config = config.replace('DOMAIN_NGINX', f'{self.host}')

        Path('/etc/nginx/conf.d/nginx.conf').touch()
        with open('/etc/nginx/conf.d/nginx.conf', 'w+') as file:
            file.write(config)
        self.write_progress('Reload nginx config')
        out = run_shell_command(['service', 'nginx', 'reload'])
        log_debug(out)
        time.sleep(3)

    ################################# main #################################

    def install(self):
        if not os.path.isdir('data'):
            os.mkdir('data')
        self.write_progress('Installing docker')
        install_docker()
        self.write_progress('Installing certbot')
        install_certbot()
        
        self.stop_existing_containers()
        
        self.write_progress('Remove existing backend sql data')
        remove_sql_data()

        self.ask_questions()
        self.start_certbot()
        
        self.write_common_env()
        self.write_matrix_env()
        self.write_jitsi_env()
        self.write_coturn_env()
        
        self.fix_coturn_config()
        self.fix_nginx_config()
        
        self.write_progress('Create synapse config')
        create_synapse_config()
        
        self.fix_synapse_config()
        self.fix_sygnal_config()
        
        self.run_docker_compose()
        self.write_progress('Installation completed', True)
        print('Complete!')
        exit()

    def update(self):
        print('Update initiated')
        print('-------------------------------')
        out = run_shell_command(self.base_docker_command + ['rm', '-sf'])
        log_debug(out)
        out = run_shell_command(self.base_docker_command + ['pull'])
        log_debug(out)
        out = run_shell_command(self.base_docker_command + ['up', '-d'])
        log_debug(out)
        show_message('Update finished!')
        exit()

    def restart(self):
        print('Restart initiated')
        print('-------------------------------')
        out = run_shell_command(self.base_docker_command + ['restart'])
        log_debug(out)
        show_message('Restart finished!')
        exit()

    def remove(self):
        out = run_shell_command(self.base_docker_command + ['stop'])
        log_debug(out)

        out = run_shell_command(self.base_docker_command + ['rm', '-svf'])
        with open('host.lock', 'r') as file:
            self.host = file.read().strip()
        remove_sql_data()
        remove_backend_data()

        self.delete_certs()

        show_message('Remove finished!')
        exit()

    def stop(self):
        print('Stop all services')
        print('-------------------------------')
        out = run_shell_command(self.base_docker_command + ['stop'])
        log_debug(out)
        show_message('Services stopped!')
        exit()

    def start(self):
        print('Start all services')
        print('-------------------------------')
        out = run_shell_command(self.base_docker_command + ['start'])
        log_debug(out)
        show_message('Services started!')
        exit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-u', '--update', action='store_true', help='Update service containers')
    group.add_argument('-i', '--install', action='store_true', help='Install Matrix Backend')
    group.add_argument('-r', '--restart', action='store_true', help='Restart all services')
    group.add_argument('-rm', '--remove', action='store_true', help='Remove all backend data and restore to factory settings')
    group.add_argument('--stop', action='store_true', help='Stop all services')
    group.add_argument('--start', action='store_true', help='Run all services')

    parser.add_argument('--domain', default=None, help='General domain name')
    parser.add_argument('--email', default=None, help='E-mail for certificates')
    parser.add_argument('--no-questions', action='store_true', help='Run script without asking questions')

    args = parser.parse_args()

    if not (args.update or args.install or args.restart or args.remove or args.stop or args.start):
        parser.error('Action required, add any option to use. You can see options by adding -h (--help) flag')

    installer = MatrixBackendStack()

    if args.install:
        show_message('Hi! This script will install your Matrix backend. For now it only capable with Ubuntu Linux',
                     title=True)

        if not args.no_questions:
            if not confirm_action('Do you setup DNS records?'):
                print('Please check Reade.md section !')
                exit()
            if not confirm_action('Do you want to start installation?'):
                exit()

        installer.init_domain_and_email(args.domain, args.email)
        installer.install()

    if args.update:
        installer.update()

    if args.restart:
        installer.restart()

    #TODO - remove certs broke nginx
    if args.remove:
        if confirm_action('WARNING! This action will remove ALL backend data and CANNOT BE CANCELLED.\nAre you sure?'):
            installer.remove()

    if args.stop:
        installer.stop()
    
    if args.start:
        installer.start()
        