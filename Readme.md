# Matrix Synapse

## Requrements

### DNS

Add next records:

```
A matrix {ip of serve} 
SRV _matrix._tcp 10 0 8448 {host}
```

### SSL certs

For now synapse not support selfsigned certs. Need to use something like letsencrypt.

Need to put crtficate and key here:

```
configs/nginx/certs/private.key 
configs/nginx/certs/tlscert.crt 
```

### Run

For run matrix synapse server run:

```bash
docker-compose up -d
```

If new configuration needed, remove `data` and `postgresdata` folders and run:

```bash
docker-compose run --rm synapse generate
```

Don't forget to edit `.env` file.

### Bugs

After generate config, need to fix logs config


```
handlers:
    file:
        class: logging.handlers.TimedRotatingFileHandler
        formatter: precise
        filename: /homeserver.log
```

`filename` to `/data/homeserver.log`