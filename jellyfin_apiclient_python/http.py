#/usr/bin/python3
# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from json import dumps
from logging import getLogger
from time import sleep
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, ReadTimeout, HTTPError, MissingSchema
from six import string_types
from .exceptions import HTTPException

#################################################################################################

global LOG # just make sure it's global'
LOG = getLogger("Jellyfin." + __name__)

#################################################################################################


class HTTP(object):
    session = None
    keep_alive = False
    def __init__(self, client):
        self.client = client
        self.config = client.config

    def start_session(self):
        """ Starts Session by mounting request session to http server """
        self.session = Session()
        max_retries = self.config.data["http.max_retries"]
        self.session.mount("http://", HTTPAdapter(max_retries = max_retries))
        self.session.mount("https://", HTTPAdapter(max_retries = max_retries))

    def stop_session(self):
        """ Stops Session by closing request Session"""
        if self.session is None:
            return
        try:
            LOG.info(f"--<[ session/{id(self.session)} ]")
            self.session.close()
        except Exception as error:
            context = error.__context__ if error.__context__ != None else ''
            cause = error.__context__ if error.__cause__ != None else ''
            LOG.warning(
                "The requests session could not be terminated:"\
                f" {error} {context} {cause}"
            )

    def _replace_user_info(self, string):
        if "{server}" in string:
            if self.config.data.get("auth.server", None):
                string = string.replace("{server}", self.config.data["auth.server"])
            else:
                LOG.debug("Server address not set")
        if "{UserId}" in string:
            if self.config.data.get("auth.user_id", None):
                string = string.replace("{UserId}", self.config.data["auth.user_id"])
            else:
                LOG.debug("UserId is not set.")
        if "{DeviceId}" in string:
            if self.config.data.get("app.device_id", None):
                string = string.replace("{DeviceId}", self.config.data["app.device_id"])
            else:
                LOG.debug("DeviceId is not set.")
        return string

    def request(self, data, session = None, dest_file = None):
        """ Give a chance to retry the connection. Jellyfin sometimes can be slow to answer back
            data dictionary can contain:
            type: GET, POST, etc.
            url: (optional)
            handler: not considered when url is provided (optional)
            params: request parameters (optional)
            json: request body (optional)
            headers: (optional),
            verify: ssl certificate, True (verify using device built-in library) or False
        """
        if not data:
            raise AttributeError("Request cannot be empty")
        data = self._request(data)
        LOG.debug(f"--->[ http ] {dumps(data, indent = 4)}", )
        retry = data.pop("retry", 5)
        stream = dest_file is not None
        while True:
            try:
                response = self._requests(
                    session or self.session or requests,
                    data.pop("type", "GET"),
                    **data, stream = stream
                )
                if stream:
                    for chunk in response.iter_content(chunk_size = 8192): 
                        if chunk: # filter out keep-alive new chunks
                            dest_file.write(chunk)
                else:
                    response.content # release the connection
                if not self.keep_alive and self.session is not None:
                    self.stop_session()
                response.raise_for_status()
            except ConnectionError as error:
                if retry:
                    retry -= 1
                    sleep(1)
                    continue
                context = error.__context__ if error.__context__ != None else ''
                cause = error.__context__ if error.__cause__ != None else ''
                LOG.error(f"{error} {context} {cause}")
                self.client.callback(
                    "ServerUnreachable", {"ServerId": self.config.data["auth.server-id"]}
                )
                raise HTTPException("ServerUnreachable", error)
            except ReadTimeout as error:
                if retry:
                    retry -= 1
                    sleep(1)
                    continue
                context = error.__context__ if error.__context__ != None else ''
                cause = error.__context__ if error.__cause__ != None else ''
                LOG.error(f"{error} {context} {cause}")
                raise HTTPException("ReadTimeout", error)
            except HTTPError as error:
                context = error.__context__ if error.__context__ != None else ''
                cause = error.__context__ if error.__cause__ != None else ''
                LOG.error(f"{error} {context} {cause}")
                if response.status_code == 401:
                    if "X-Application-Error-Code" in response.headers:
                        self.client.callback(
                            "AccessRestricted", {"ServerId": self.config.data["auth.server-id"]}
                        )
                        raise HTTPException("AccessRestricted", error)
                    else:
                        self.client.callback(
                            "Unauthorized", {"ServerId": self.config.data["auth.server-id"]}
                        )
                        self.client.auth.revoke_token()
                        raise HTTPException("Unauthorized", error)
                elif response.status_code == 500: # log and ignore.
                    context = error.__context__ if error.__context__ != None else ''
                    cause = error.__context__ if error.__cause__ != None else ''
                    LOG.error(f"--[ 500 response ] {error} {context} {cause}")
                    return
                elif response.status_code == 502:
                    if retry:
                        retry -= 1
                        sleep(1)
                        continue
                raise HTTPException(response.status_code, error)
            except MissingSchema as error:
                context = error.__context__ if error.__context__ != None else ''
                cause = error.__context__ if error.__cause__ != None else ''
                LOG.error(f"Request missing Schema. {error} {context} {cause}"))
                raise HTTPException(
                    "MissingSchema", {"Id": self.config.data.get("auth.server", "None")}
                )
            except Exception as error:
                context = error.__context__ if error.__context__ != None else ''
                cause = error.__context__ if error.__cause__ != None else ''
                LOG.error(f"--[ 500 response ] {error} {context} {cause}")
                raise error
            else:
                try:
                    if stream:
                        return
                    self.config.data["server-time"] = response.headers["Date"]
                    elapsed = int(response.elapsed.total_seconds() * 1000)
                    response = response.json()
                    LOG.debug(f"---<[ http ][{elapsed} ms]")
                    LOG.debug(dumps(response, indent = 4))
                    return response
                except ValueError:
                    return

    def _request(self, data):
        if "url" not in data:
            data["url"] = f"{self.config.data.get('auth.server', '')}"\
            f"/{data.pop('handler', '')}"
        self._get_header(data)
        data["timeout"] = data.get("timeout") or self.config.data["http.timeout"]
        data["verify"] = data.get("verify") or self.config.data.get("auth.ssl", False)
        data["url"] = self._replace_user_info(data["url"])
        self._process_params(data.get("params") or dict()) # {} can also mean set
        self._process_params(data.get("json") or dict())
        return data

    def _process_params(self, params):
        for key in params:
            value = params[key]
            if isinstance(value, dict):
                self._process_params(value)
            if isinstance(value, string_types):
                params[key] = self._replace_user_info(value)

    def _get_header(self, data):
        data["headers"] = data.setdefault("headers", {})
        if not data["headers"]:
            recent_config = ''\
            f"{self.config.data.get('app.name', 'Jellyfin for Kodi')}"/
            f"/{self.config.data.get('app.version', '0.0.0')}"
            data["headers"].update({
                "Content-type": "application/json",
                "Accept-Charset": "UTF-8,*",
                "Accept-encoding": "gzip",
                "User-Agent": self.config.data["http.user_agent"] or recent_config
            })
        if "x-emby-authorization" not in data["headers"]:
            self._authorization(data)
        return data

    def _authorization(self, data):
        auth = "MediaBrowser "
        auth += f"Client = {self.config.data.get('app.name', 'Jellyfin for Kodi')}, "
        auth += f"Device = {self.config.data.get('app.device_name', 'Unknown Device')}, "
        auth += f"DeviceId = {self.config.data.get('app.device_id', 'Unknown Device id')}, "
        auth += f"Version = {self.config.data.get('app.version', '0.0.0')}"
        data["headers"].update({"x-emby-authorization": auth})
        if self.config.data.get("auth.token") and self.config.data.get("auth.user_id"):
            auth += f", UserId = {self.config.data.get('auth.user_id')}"
            data["headers"].update({"x-emby-authorization": auth, "X-MediaBrowser-Token": self.config.data.get("auth.token")})
        return data

    def _requests(self, session, action, **kwargs):
        if action == "GET":
            return session.get(**kwargs)
        elif action == "POST":
            return session.post(**kwargs)
        elif action == "HEAD":
            return session.head(**kwargs)
        elif action == "DELETE":
            return session.delete(**kwargs)
