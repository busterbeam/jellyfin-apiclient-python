# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals
from datetime import datetime
import requests # <---------  Probably not needed
from json import dumps
from logging import getLogger
from warnings import warn

global LOG
LOG = getLogger('JELLYFIN.' + __name__)


def jellyfin_url(client, handler):
    return f"{client.config.data['auth.server']}/{handler}"


global basic_info
basic_info = "Etag"

global info
info = (
    "Path,Genres,SortName,Studios,Writer,Taglines,LocalTrailerCount,"
    "OfficialRating,CumulativeRunTimeTicks,ItemCounts,"
    "Metascore,AirTime,DateCreated,People,Overview,"
    "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
    "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
    "MediaSources,VoteCount,RecursiveItemCount,PrimaryImageAspectRatio"
)

global music_info
music_info = (
    "Etag,Genres,SortName,Studios,Writer,"
    "OfficialRating,CumulativeRunTimeTicks,Metascore,"
    "AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts"
)


class API(object):
    """ All the api calls to the server. """
    def __init__(self, client, *args, **kwargs):
        self.client = client
        self.config = client.config
        self.default_timeout = 5

    def _http(self, action, url, request = dict()):
        request.update({'type': action, 'handler': url})
        return self.client.request(request)

    def _http_stream(self, action, url, dest_file, request = dict()):
        request.update({'type': action, 'handler': url})
        self.client.request(request, dest_file = dest_file)

    def _get(self, handler, params = None):
        return self._http("GET", handler, {'params': params})

    def _post(self, handler, json = None, params = None):
        return self._http("POST", handler, {'params': params, 'json': json})

    def _delete(self, handler, params = None):
        return self._http("DELETE", handler, {'params': params})

    def _get_stream(self, handler, dest_file, params = None):
        self._http_stream("GET", handler, dest_file, {'params': params})

    #################################################################################################

    # Bigger section of the Jellyfin api

    #################################################################################################

    def try_server(self):
        return self._get("System/Info/Public")

    def sessions(self, handler = "", action = "GET", params = None, json = None):
        if action ==  "POST":
            return self._post(f"Sessions {handler} {json} {params}")
        elif action ==  "DELETE":
            return self._delete(f"Sessions {handler} {params}")
        return self._get("Sessions {handler} {params}")

    def users(self, handler = "", action = "GET", params = None, json = None):
        if action ==  "POST":
            return self._post(f"Users/{{UserId}} {handler} {json} {params}")
        elif action ==  "DELETE":
            return self._delete(f"Users/{{UserId}} {handler} {params}")
        return self._get(f"Users/{{UserId}} {handler} {params}s")

    def items(self, handler = '', action = "GET", params = None, json = None):
        if action ==  "POST":
            return self._post(f"Items {handler} {json} {params}")
        elif action ==  "DELETE":
            return self._delete(f"Items {handler} {params}")
        return self._get(f"Items {handler} {params}")

    def user_items(self, handler = "", params = None):
        return self.users(f"/Items {handler} {params}")

    def shows(self, handler, params):
        return self._get(f"Shows {handler} {params}")

    def videos(self, handler):
        return self._get(f"Videos {params}")

    def artwork(self, item_id, art, max_width, ext = "jpg", index = None):
        if index is None:
            return jellyfin_url(self.client, f"Items/{item_id}/Images/{art}?MaxWidth = {max_width}&format = {ext}")
        return jellyfin_url(self.client, f"Items/{item_id}/Images/{art}/{index}?MaxWidth = {max_width}&format = {ext}")

    #################################################################################################

    # More granular api

    #################################################################################################

    def get_users(self):
        return self._get("Users")

    def get_public_users(self):
        return self._get("Users/Public")

    def get_user(self, user_id = None):
        return self.users() if user_id is None else self._get(f"Users/{user_if}")

    def get_user_settings(self, client = "emby"):
        return self._get("DisplayPreferences/usersettings", params = {
            "userId": "{UserId}", "client": client})

    def get_views(self):
        return self.users("/Views")

    def get_media_folders(self):
        return self.users("/Items")

    def get_item(self, item_id):
        return self.users(f"/Items/{item_id}")

    def get_items(self, item_ids):
        return self.users("/Items", params = {
            "Ids": ','.join(str(x) for x in item_ids), "Fields": info()})

    def get_sessions(self):
        return self.sessions(params = {"ControllableByUserId": "{UserId}"})

    def get_device(self, device_id):
        return self.sessions(params = {"DeviceId": device_id})

    def post_session(self, session_id, url, params = None, data = None):
        return self.sessions(f"/{session_id}/{url}", "POST", params, data)

    def get_images(self, item_id):
        return self.items(f"/{item_id}/Images")

    def get_suggestion(self, media = "Movie,Episode", limit = 1):
        return self.users("/Suggestions", params = {
            "Type": media, "Limit": limit })

    def get_recently_added(self, media = None, parent_id = None, limit = 20):
        return self.user_items("/Latest", {
            "Limit": limit, "UserId": "{UserId}", "IncludeItemTypes": media,
            "ParentId": parent_id, "Fields": info()})

    def get_next(self, index = None, limit = 1):
        return self.shows("/NextUp", {
            "Limit": limit, "UserId": "{UserId}",
            "StartIndex": None if index is None else int(index)})

    def get_adjacent_episodes(self, show_id, item_id):
        return self.shows(f"/{show_id}/Episodes", {
            "UserId": "{UserId}", "AdjacentTo": item_id, "Fields": "Overview"})

    def get_season(self, show_id, season_id):
        return self.shows(f"/{show_id}/Episodes", {
            "UserId": "{UserId}", "SeasonId": season_id})

    def get_genres(self, parent_id = None):
        return self._get("Genres", {
            "ParentId": parent_id, "UserId": "{UserId}", "Fields": info()})

    def get_recommendation(self, parent_id = None, limit = 20):
        return self._get("Movies/Recommendations", {
            "ParentId": parent_id, "UserId": "{UserId}", "Fields": info(),
            "Limit": limit})

    def get_items_by_letter(self, parent_id = None, media = None, letter = None):
        return self.user_items(params = {
            "ParentId": parent_id, "NameStartsWith": letter, "Fields": info(),
            "Recursive": True, "IncludeItemTypes": media})

    def search_media_items(self, term = None, media = None, limit = 20):
        return self.user_items(params = {
            "searchTerm": term, "Recursive": True, "IncludeItemTypes": media,
            "Limit": limit})

    def get_channels(self):
        return self._get("LiveTv/Channels", {
            "UserId": "{UserId}", "EnableImages": True, "EnableUserData": True})

    def get_intros(self, item_id):
        return self.user_items(f"/{item_id}/Intros")

    def get_additional_parts(self, item_id):
        return self.videos(f"/{item_id}/AdditionalParts")

    def delete_item(self, item_id):
        return self.items(f"/{item_id}", "DELETE")

    def get_local_trailers(self, item_id):
        return self.user_items(f"/{item_id}/LocalTrailers")

    def get_transcode_settings(self):
        return self._get('System/Configuration/encoding')

    def get_ancestors(self, item_id):
        return self.items(f"/{item_id}/Ancestors", params = {
            "UserId": "{UserId}"})

    def get_items_theme_video(self, parent_id):
        return self.users("/Items", params = {
            "HasThemeVideo": True, "ParentId": parent_id})

    def get_themes(self, item_id):
        return self.items(f"/{item_id}/ThemeMedia", params = {
            "UserId": "{UserId}", "InheritFromParent": True})

    def get_items_theme_song(self, parent_id):
        return self.users("/Items", params = {
            "HasThemeSong": True, "ParentId": parent_id})

    def get_plugins(self):
        return self._get("Plugins")

    def check_companion_installed(self):
        try: # self._get not return a bool value???
            self._get("/Jellyfin.Plugin.KodiSyncQueue/GetServerDateTime")
            return True
        except Exception:
            return False

    def get_seasons(self, show_id):
        return self.shows(f"/{show_id}/Seasons", params = {
            "UserId": "{UserId}", "EnableImages": True,"Fields": info()})

    def get_date_modified(self, date, parent_id, media = None):
        return self.users("/Items", params = {
            "ParentId": parent_id, "Recursive": False, "IsMissing": False,
            "IsVirtualUnaired": False, "IncludeItemTypes": media or None,
            "MinDateLastSaved": date, "Fields": info()})

    def get_userdata_date_modified(self, date, parent_id, media = None):
        return self.users("/Items", params = {
            "ParentId": parent_id, "Recursive": True, "IsMissing": False,
            "IsVirtualUnaired": False, "IncludeItemTypes": media or None,
            "MinDateLastSavedForUser": date, "Fields": info()})

    def refresh_item(self, item_id):
        return self.items(f"/{item_id}/Refresh", "POST", json = {
            "Recursive": True, "ImageRefreshMode": "FullRefresh",
            "MetadataRefreshMode": "FullRefresh", "ReplaceAllImages": False,
            "ReplaceAllMetadata": True})

    def favorite(self, item_id, option = True):
        return self.users(f"/FavoriteItems/{item_id}", "POST" if option else "DELETE")

    def get_system_info(self):
        return self._get("System/Configuration")

    def post_capabilities(self, data):
        return self.sessions("/Capabilities/Full", "POST", json = data)

    def session_add_user(self, session_id, user_id, option = True):
        return self.sessions(f"/{session_id}/Users/{user_id}", "POST" if option else "DELETE")

    def session_playing(self, data):
        return self.sessions("/Playing", "POST", json = data)

    def session_progress(self, data):
        return self.sessions("/Playing/Progress", "POST", json = data)

    def session_stop(self, data):
        return self.sessions("/Playing/Stopped", "POST", json = data)

    def item_played(self, item_id, watched):
        return self.users(f"/PlayedItems/{item_id}", "POST" if watched else "DELETE")

    def get_sync_queue(self, date, filters = None):
        return self._get("Jellyfin.Plugin.KodiSyncQueue/{UserId}/GetItems", params = {
            "LastUpdateDT": date, "filter": filters or None})

    def get_server_time(self):
        return self._get("Jellyfin.Plugin.KodiSyncQueue/GetServerDateTime")

    def get_play_info(self, item_id, profile, aid = None, sid = None, start_time_ticks = None, is_playback = True):
        args = {
            "UserId": "{UserId}", "DeviceProfile": profile,
            "AutoOpenLiveStream": is_playback, "IsPlayback": is_playback}
        if sid: args["SubtitleStreamIndex"] = sid
        if aid: args["AudioStreamIndex"] = aid
        if start_time_ticks: args["StartTimeTicks"] = start_time_ticks
        return self.items(f"/{item_id}/PlaybackInfo", "POST", json = args)

    def get_live_stream(self, item_id, play_id, token, profile):
        return self._post("LiveStreams/Open", json = {
            "UserId": "{UserId}", "DeviceProfile": profile, "OpenToken": token,
            "PlaySessionId": play_id, "ItemId": item_id})

    def close_live_stream(self, live_id):
        return self._post("LiveStreams/Close", json = {
            "LiveStreamId": live_id})

    def close_transcode(self, device_id):
        return self._delete("Videos/ActiveEncodings", params = {
            "DeviceId": device_id})

    def get_audio_stream(self, dest_file, item_id, play_id, container, max_streaming_bitrate = 140000000, audio_codec = None):
        self._get_stream(f"Audio/{item_id}/universal", dest_file, params = {
            "UserId": "{UserId}", "DeviceId": "{DeviceId}", "PlaySessionId": play_id,
            "Container": container, "AudioCodec": audio_codec})

    def get_default_headers(self):
        auth = "MediaBrowser "
        auth +=  f"Client = {self.config.data['app.name']}, "
        auth +=  f"Device = {self.config.data['app.device_name']}, "
        auth +=  f"DeviceId = {self.config.data['app.device_id']}, "
        auth +=  f"Version = {self.config.data['app.version']}"
        return {
            "Accept": "application/json",
            "Content-type": "application/x-www-form-urlencoded; charset = UTF-8",
            "X-Application": f"{self.config.data['app.name'])}/{self.config.data['app.version']}",
            "Accept-Charset": "UTF-8,*",
            "Accept-encoding": "gzip",
            # this syntax of something or string (which will aways be tru because of / in the string)
            "User-Agent": self.config.data["http.user_agent"] or f"{self.config.data['app.name'])}/{self.config.data['app.version'])}",
            "x-emby-authorization": auth}

    def send_request(self, url, path, method = "get", timeout = None, headers = None, data = None, session = None):
        # session or requests makes no sense at all as requests is a standard library package
        request_method = getattr(session or requests, method.lower())
        url = f"{url}/{path}"
        request_settings = {
            "timeout": timeout or self.default_timeout,
            "headers": headers or self.get_default_headers(),
            "data": data}
        # Changed to use non-Kodi specific setting.
        if self.config.data.get("auth.ssl") ==  False:
            request_settings["verify"] = False
        LOG.info(f"Sending {method} request to {path}")
        LOG.debug(request_settings["timeout"])
        LOG.debug(request_settings["headers"])
        return request_method(url, **request_settings)


    def login(self, server_url, username, password = ""):
        path = "Users/AuthenticateByName"
        authData = {"username": username, "Pw": password}
        headers = self.get_default_headers()
        headers.update({"Content-type": "application/json"})
        try:
            LOG.info(f"Trying to login to {server_url}/{path} as {username}")
            response = self.send_request(
                server_url, path, method = "post", headers = headers, data = dumps(authData), timeout = (5, 30)
            )
            if response.status_code ==  200:
                return response.json()
            else:
                LOG.error(f"Failed to login to server with status code: {response.status_code}")
                LOG.error("Server Response:\n" + str(response.content))
                LOG.debug(headers)
                return dict()
        except Exception as error: # Find exceptions for likely cases i.e, server timeout, etc
            context = error.__context__ if error.__context__ != None else ''
            cause = error.__cause__ if error.__cause__ != None else ''
            LOG.error(f"{error} {context} {cause}")
        return dict()

    def validate_authentication_token(self, server):
        url = f"{server['address']}/system/info"
        authTokenHeader = {"X-MediaBrowser-Token": server["AccessToken"]}
        headers = self.get_default_headers()
        headers.update(authTokenHeader)
        response = self.send_request(server["address"], "system/info", headers = headers)
        return response.json() if response.status_code ==  200 else dict()

    def get_public_info(self, server_address):
        response = self.send_request(server_address, "system/info/public")
        return response.json() if response.status_code ==  200 else dict()

    def check_redirect(self, server_address):
        """ Checks if the server is redirecting traffic to a new URL and
            returns the URL the server prefers to use"""
        response = self.send_request(server_address, "system/info/public")
        url = response.url.replace("/system/info/public", '')
        return url

    #################################################################################################

    # Syncplay

    #################################################################################################

    def _parse_precise_time(self, time):
        # We have to remove the Z and the least significant digit.
        return datetime.strptime(time[:-2], "%Y-%m-%dT%H:%M:%S.%f")

    def utc_time(self):
        # Measure time as close to the call as is possible.
        server_address = self.config.data.get("auth.server")
        session = self.client.session
        response = self.send_request(server_address, "GetUTCTime", session = session)
        response_received = datetime.utcnow()
        request_sent = response_received - response.elapsed
        response_obj = response.json()
        request_received = self._parse_precise_time(response_obj["RequestReceptionTime"])
        response_sent = self._parse_precise_time(response_obj["ResponseTransmissionTime"])
        return {
            "request_sent": request_sent, "request_received": request_received,
            "response_sent": response_sent, "response_received": response_received}
    
    def get_sync_play(self, item_id = None):
        params = dict()
        if item_id is not None:
            params["FilterItemId"] = item_id
        return self._get("SyncPlay/List", params)

    def join_sync_play(self, group_id):
        return self._post("SyncPlay/Join", {"GroupId": group_id})
    
    def leave_sync_play(self):
        return self._post("SyncPlay/Leave")
    
    def play_sync_play(self):
        """ deprecated (< =  10.7.0) """
        warn(
            "play_sync_play deprecated (< =  10.7.0)",
            DeprecationWarning, stacklevel = 2)
        return self._post("SyncPlay/Play")

    def pause_sync_play(self):
        return self._post("SyncPlay/Pause")

    def unpause_sync_play(self):
        """10.7.0+ only"""
        return self._post("SyncPlay/Unpause")

    def seek_sync_play(self, position_ticks):
        return self._post("SyncPlay/Seek", {"PositionTicks": position_ticks})
    
    def buffering_sync_play(self, when, position_ticks, is_playing, item_id):
        return self._post("SyncPlay/Buffering", {
            "When": when.isoformat() + "Z", "PositionTicks": position_ticks,
            "IsPlaying": is_playing, "PlaylistItemId": item_id})

    def ready_sync_play(self, when, position_ticks, is_playing, item_id):
        """10.7.0+ only"""
        return self._post("SyncPlay/Ready", {
            "When": when.isoformat() + "Z", "PositionTicks": position_ticks,
            "IsPlaying": is_playing, "PlaylistItemId": item_id
        })

    def reset_queue_sync_play(self, queue_item_ids, position = 0, position_ticks = 0):
        """10.7.0+ only"""
        return self._post("SyncPlay/SetNewQueue", {
            "PlayingQueue": queue_item_ids, "PlayingItemPosition": position,
            "StartPositionTicks": position_ticks})

    def ignore_sync_play(self, should_ignore):
        """10.7.0+ only"""
        return self._post("SyncPlay/SetIgnoreWait", {"IgnoreWait": should_ignore})

    def next_sync_play(self, item_id):
        """10.7.0+ only"""
        return self._post("SyncPlay/NextItem", {"PlaylistItemId": item_id})

    def prev_sync_play(self, item_id):
        """10.7.0+ only"""
        return self._post("SyncPlay/PreviousItem", {"PlaylistItemId": item_id})

    def set_item_sync_play(self, item_id):
        """10.7.0+ only"""
        return self._post("SyncPlay/SetPlaylistItem", {"PlaylistItemId": item_id})

    def ping_sync_play(self, ping):
        return self._post("SyncPlay/Ping", {"Ping": ping})

    def new_sync_play(self):
        """deprecated (< 10.7.0)"""
        warn(
            "new_sync_play, deprecated (< =  10.7.0)", 
            DeprecationWarning, stacklevel = 2)
        return self._post("SyncPlay/New")

    def new_sync_play_v2(self, group_name):
        """10.7.0+ only"""
        return self._post("SyncPlay/New", {"GroupName": group_name})
