#!/usr/bin/env python3

import re
from urllib.parse import urljoin

import yaml
import requests
import lxml.html
import sys
import schedule
import time
import os
import signal
import logging
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

set_header_str = "proxy_set_header Cookie \"{}\"; # AUTO-GENERATED DO NOT EDIT"
set_header_regex = re.compile(set_header_str.format("(.*?)"))

env = Environment(
    loader=FileSystemLoader('/app'),
)
config_template = env.get_template('misp-proxy.conf.j2')


def read_cookies_from_config(config_file):
    with open(config_file) as fp:
        config_file_contents = fp.read()

    match = next(iter(set_header_regex.finditer(config_file_contents)), None)
    if match:
        cookie_str = match.group(1)
        return {k: v for k, v in (i.rstrip(";").split("=", maxsplit=1) for i in cookie_str.split())}


def write_config(config, config_file):
    new_config_contents = config_template.render(**config)
    with open(config_file, "r") as fp:
        old_config_contents = fp.read()
    if new_config_contents != old_config_contents:
        with open(config_file, "w") as fp:
            fp.write(new_config_contents)
        logging.info(f"{config_file} contents have been updated")
        return True
    return False


class MispProxyConfigurator(object):
    def __init__(self, config_file, nginx_conf=None):
        with open(config_file) as fp:
            self.config = yaml.load(fp, Loader=yaml.SafeLoader)
            self.nginx_conf = nginx_conf or self.config.get("nginx_conf", "/etc/nginx/conf.d/default.conf")
            self.base_url = self.config["backend"]
            self.login_url = urljoin(self.base_url, "/users/login")

    def __call__(self):
        logging.info("Checking nginx misp-proxy configuration")
        cookies = read_cookies_from_config(self.nginx_conf)
        if not cookies or not self.check_login(cookies):
            logging.info(f"Cookies present in {self.nginx_conf} are invalid, logging in again")
            self.config["cookies"] = "; ".join(
                f"{k}={v}" for k, v in self.login(self.config['user'], self.config['pass']).items())

        if write_config(self.config, self.nginx_conf):
            logging.info("Sending SIGHUP to PID 1")
            os.kill(1, signal.SIGHUP)

    def login(self, username, password):
        session = requests.session()
        doc = lxml.html.fromstring(session.get(self.login_url).content)
        form = doc.xpath("//form[@id='UserLoginForm']")[0]
        session.request(
            form.attrib['method'],
            urljoin(self.base_url, form.attrib['action']),
            data={
                **{
                    e.attrib['name']: e.attrib['value']
                    for e in form.xpath("//input[@type='hidden']")
                    if 'name' in e.attrib
                },
                "data[User][email]": username,
                "data[User][password]": password
            })
        return dict(session.cookies)

    def check_login(self, cookies):
        return requests.get(
            self.base_url, cookies=cookies, allow_redirects=False
        ).headers.get("Location") != self.login_url


if __name__ == '__main__':
    configurator = MispProxyConfigurator(sys.argv[1])
    configurator()
    schedule.every(10).minutes.do(configurator)

    while True:
        schedule.run_pending()
        time.sleep(1)
