#!/bin/bash

"${mysql[@]}" <<-EOSQL
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE_2\` ;
GRANT ALL ON \`$MYSQL_DATABASE_2\`.* TO '$MYSQL_USER'@'%' ;
EOSQL