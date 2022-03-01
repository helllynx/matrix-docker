# Aura Project

## Минимальные требования (приблизительные)

Для клиентской базы < 200

* CPU: 8 core
* RAM: 16 GB
* SSD: 256 GB
* SWAP: 32 GB


## Установка

### Настройка DNS

Для корректной работы бекенда необходимо настроить следующие записи `DNS`:

```
A matrix {server ip}
A meet {server ip}
SRV _matrix._tcp 10 0 8448 {server ip}
```

### Установка Backend

Для установки выполнить

```
$ python3 aura.py -i

####### Hi! This script will install your Aura backend. For now it only capable with Ubuntu Linux #######

Do you want to start installation? [Y/n]: Y
Please enter next mandatory information:
Domain for services: example.com
Confirm Domain for services: example.com
Email: test@example.com
Confirm Email: test@example.com
```
Скрипт спросит домен и почту для генерации сертификатов `LetsEncrypt`, установит `docker` и развернет сервисы.
