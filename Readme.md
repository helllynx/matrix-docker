# Matrix Synapse

## Requrements

### DNS

Add next records:

```
A matrix {server ip} 
SRV _matrix._tcp 10 0 8448 {server ip}
```

### SSL certs

For now synapse not support selfsigned certs. Need to use something like letsencrypt.

For manual setup user this isntruction https://certbot.eff.org/lets-encrypt/ubuntufocal-other

### Run

For run matrix synapse server run:

```bash
docker-compose up -d
```

If new configuration needed, remove `data` and `postgresdata` folders and run:

```bash
docker-compose run --rm synapse generate
```

### Config

Can be added after generation:

```yaml
public_baseurl: https://example.org/

ip_range_whitelist:
  - '127.0.0.1/8'
  - '0.0.0.0/8'
  - '10.0.0.0/8'
  - '172.16.0.0/12'
  - '192.168.0.0/16'
  - '100.64.0.0/10'
  - '169.254.0.0/16'
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


