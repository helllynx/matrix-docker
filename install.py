import argparse
import logging
import os
import random
import shutil
import string
import subprocess
from pathlib import Path

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


def stop_existing_containers():
    log_debug('stop running containers')
    show_message('Stop running proxy containers if exists')
    out = run_shell_command(['docker-compose',
                             '-f', 'docker-compose.jitsi.yml',
                             '-f', 'docker-compose.matrix.yml',
                             'down'])
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


def remove_media():
    log_debug('remove media dir')
    show_message('Remove existing media data')
    if os.path.isdir('media'):
        shutil.rmtree('media')


def get_confirmed_inputed_value(text):
    value = input(text).strip()
    if confirm_value(value, text):
        return value
    print('Confirm value was wrong, please retype value')
    return get_confirmed_inputed_value(text)


def create_synapse_config():
    log_debug('create_synapse_config')
    run_shell_command(['docker-compose', '-f', 'docker-compose.matrix.yml', 'run', '--rm', 'synapse', 'generate'])


def run_docker_compose():
    log_debug('run_docker_compose')
    run_shell_command(['docker-compose',
                       '-f', 'docker-compose.jitsi.yml',
                       '-f', 'docker-compose.matrix.yml',
                       'up', '-d'])


def get_env_data_as_dict(path: str) -> dict:
    with open(path, 'r') as f:
        return dict(tuple(line.replace('\n', '').split('=')) for line in f.readlines() if
                    not (line.startswith('#') or len(line.strip()) == 0))


class MatrixBackend:

    def __init__(self):
        self.synapse_db_password = generate_password()
        self.host = None
        self.email = None
        self.turn_shared_secret = generate_password(64)
        self.coturn_db_password = generate_password(16)

    def ask_questions(self):
        log_debug('ask_questions')
        show_message('Please enter next mandatory information:')
        self.host = get_confirmed_inputed_value('Domain for services: ')
        self.email = get_confirmed_inputed_value('Email: ')

    def start_certbot(self):
        log_debug('start_certbot')
        if (os.path.isfile(f'/etc/letsencrypt/live/matrix.{self.host}/fullchain.pem') and
                os.path.isfile(f'/etc/letsencrypt/live/api.{self.host}/fullchain.pem') and
                os.path.isfile(f'/etc/letsencrypt/live/meet.{self.host}/fullchain.pem')):
            show_message('Certificate already exists. Skipping...')
            return
        show_message('Start getting certbot files')
        # TODO ISSUE HERE, certbot takes only first -d arg
        out = run_shell_command(
            ['certbot', 'certonly', '--standalone', '-n', '--agree-tos', '--email', self.email, '-d',
             f'api.{self.host}', '-d', f'matrix.{self.host}', '-d', f'meet.{self.host}', '--expand'])
        log_debug(out)

    def write_jitsi_env(self):
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


    def write_coturn_env(self):
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

        with open('data/synapse/homeserver.yaml', 'w+') as file:
            file.write(yaml.dump(config))

    def fix_coturn_config(self):
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
        with open('configs/sygnal/sygnal.yaml', 'r') as file:
            try:
                config = yaml.safe_load(file)
            except yaml.YAMLError as exc:
                log_debug(exc)

        # TODO replace api_key and app package with env variable
        config['apps']['im.vector.app.android:'] = {
            'type': 'gcm',
            'api_key': '',
        }

        with open('configs/sygnal/sygnal.yaml', 'w+') as file:
            file.write(yaml.dump(config))

    def fix_nginx_config(self):
        with open('configs/nginx/nginx-conf.template', 'r') as file:
            config = file.read()

        config = config.replace('DOMAIN_NGINX', f'{self.host}')

        Path('configs/nginx/nginx.conf').touch()
        with open('configs/nginx/nginx.conf', 'w+') as file:
            file.write(config)

    def install(self):
        install_docker()
        install_certbot()
        
        stop_existing_containers()
        
        remove_sql_data()

        self.ask_questions()
        self.start_certbot()
        
        self.write_matrix_env()
        self.write_jitsi_env()
        self.write_coturn_env()
        
        self.fix_coturn_config()
        self.fix_nginx_config()
        
        create_synapse_config()
        
        self.fix_synapse_config()
        self.fix_sygnal_config()
        
        run_docker_compose()

        print('Complete!')

    def update(self):
        base_command = ['docker-compose',
                        '-f', 'docker-compose.jitsi.yml',
                        '-f', 'docker-compose.matrix.yml']
        out = run_shell_command(base_command + ['down'])
        log_debug(out)
        out = run_shell_command(base_command + ['pull'])
        log_debug(out)
        out = run_shell_command(base_command + ['up', '-d'])
        log_debug(out)
        show_message('Update finished!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-u', '--update', action='store_true', help='Update service containers')
    group.add_argument('-i', '--install', action='store_true', help='Install Synapse + Jitsi')

    args = parser.parse_args()

    if not (args.update or args.install):
        parser.error('Action required, add any option to use. You can see options by adding -h (--help) flag')

    installer = MatrixBackend()

    if args.install:
        show_message('Hi! This script will install your Matrix Synapse backend. For now it only capable with Ubuntu Linux',
                     title=True)
        if confirm_action('Do you want to start installation?'):
            installer.install()

    if args.update:
        installer.update()
