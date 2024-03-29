#!/bin/bash
if [ -f .env ]
then
  export $(cat .env | sed 's/#.*//g' | xargs)
fi

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER coturn;
    CREATE DATABASE coturn;
    ALTER USER coturn WITH PASSWORD '${COTURN_PASSWORD}';
    GRANT ALL PRIVILEGES ON DATABASE coturn TO coturn;
EOSQL


psql -v ON_ERROR_STOP=1 --username coturn --dbname coturn <<-EOSQL
    CREATE TABLE turnusers_lt (
        realm varchar(127) default '',
        name varchar(512),
        hmackey char(128),
        PRIMARY KEY (realm,name)
    );

    CREATE TABLE turn_secret (
        realm varchar(127) default '',
        value varchar(256),
        primary key (realm,value)
    );

    CREATE TABLE allowed_peer_ip (
        realm varchar(127) default '',
        ip_range varchar(256),
        primary key (realm,ip_range)
    );

    CREATE TABLE denied_peer_ip (
        realm varchar(127) default '',
        ip_range varchar(256),
        primary key (realm,ip_range)
    );

    CREATE TABLE turn_origin_to_realm (
        origin varchar(127),
        realm varchar(127),
        primary key (origin)
    );

    CREATE TABLE turn_realm_option (
        realm varchar(127) default '',
        opt varchar(32),
        value varchar(128),
        primary key (realm,opt)
    );

    CREATE TABLE oauth_key (
        kid varchar(128),
        ikm_key varchar(256),
        timestamp bigint default 0,
        lifetime integer default 0,
        as_rs_alg varchar(64) default '',
        realm varchar(127),
        primary key (kid)
    );

    CREATE TABLE admin_user (
        name varchar(32),
        realm varchar(127),
        password varchar(127),
        primary key (name)
    );    
EOSQL
