#!/bin/bash

sudo yum install git python-pip -y
pip install pip --upgrade
pip install streamlit boto3
git clone https://github.com/kyopark2014/llm-streamlit
python3 -m venv venv
source venv/bin/activate

sudo sh -c "cat <<EOF > /etc/systemd/system/streamlit.service
[Unit]
Description=Streamlit
After=network-online.target

[Service]
User=ec2-user
Group=ec2-user
Restart=always
ExecStart=/home/ec2-user/.local/bin/streamlit run /home/ec2-user/llm-streamlit/application/app.py

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl enable streamlit.service

sudo systemctl start streamlit
sudo systemctl status streamlit -l