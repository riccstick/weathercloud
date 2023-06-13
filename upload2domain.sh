#! /usr/bin/bash

DIR="/home/ricci/weathercloud"

curl -T $DIR/'Regen (mm).png' -u prandstritzko.:J0cJ*vY2f ftp://www.prand-stritzko.at/httpdocs/wp-content/uploads/weather/

curl -T $DIR/'Temperatur (°C).png' -u prandstritzko.:J0cJ*vY2f ftp://www.prand-stritzko.at/httpdocs/wp-content/uploads/weather/
