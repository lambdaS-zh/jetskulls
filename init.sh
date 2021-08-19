#!/bin/sh
mkdir -p ~/.jetskulls

if [ -n "$(which python)" ]; then
    py_bin="$(which python)"
elif [ -n "$(which python3)" ]; then
    py_bin="$(which python3)"
elif [ -n "$(which python2)" ]; then
    py_bin="$(which python2)"
else
    echo "python not found!"
    exit 1
fi

if [ ! -n $(which pip) ]; then
    echo "pip not found!"
    exit 1
fi

py_bin2=$(echo $py_bin | sed 's/\//\\\//g')
sed "s/ JETSKULLS-CLI/!$py_bin2/g" templates/jetskulls.py > jetskulls
chmod +x jetskulls

pip install -r requirements.txt

