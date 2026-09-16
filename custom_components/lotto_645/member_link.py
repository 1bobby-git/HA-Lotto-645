"""Member-approved connection. No browser password or shared secret in HA."""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import re
import secrets
import time

import aiohttp
from .lab_client import LabServiceError, CLIENT_USER_AGENT

ORIGIN='https://lottolab.toiss.kr'
CLIENT_ID='ha-lotto-645'
GRANT='urn:ietf:params:oauth:grant-type:device_code'


async def request(session, path, body):
    try:
        async with session.post(ORIGIN+path,json=body,headers={'Accept':'application/json','User-Agent':CLIENT_USER_AGENT},
                                timeout=aiohttp.ClientTimeout(total=15),allow_redirects=False,ssl=True) as response:
            if response.content_type!='application/json':raise LabServiceError('member_service_unavailable')
            parts=[];length=0
            async for part in response.content.iter_chunked(2048):
                length+=len(part)
                if length>16384:raise LabServiceError('invalid_member_response')
                parts.append(part)
            value=json.loads(b''.join(parts))
            if not isinstance(value,dict):raise LabServiceError('invalid_member_response')
            if response.status!=200:
                code=value.get('error')
                allowed={'authorization_pending','slow_down','expired_token','access_denied','invalid_grant','device_limit','device_already_owned'}
                raise LabServiceError(code if code in allowed else 'member_service_unavailable')
            return value
    except (aiohttp.ClientError,asyncio.TimeoutError,ValueError) as exc:
        raise LabServiceError('member_service_unavailable') from exc


def valid_tokens(raw):
    if raw.get('token_type')!='Bearer' or type(raw.get('expires_in')) is not int or not 60<=raw['expires_in']<=3600:
        raise LabServiceError('invalid_member_response')
    for key in ('access_token','refresh_token'):
        if not isinstance(raw.get(key),str) or not re.fullmatch('[A-Za-z0-9_-]{32,128}',raw[key]):
            raise LabServiceError('invalid_member_response')
    if not re.fullmatch('[0-9a-f]{32}',str(raw.get('device_id',''))):raise LabServiceError('invalid_member_response')
    return {key:raw[key] for key in ('access_token','refresh_token','device_id','expires_in')}


async def start(session, legacy=None):
    verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    body={'client_id':CLIENT_ID,'code_challenge':challenge,'code_challenge_method':'S256','device_name':'Home Assistant'}
    if legacy and legacy.get('source') in ('operator','automatic','member'):
        # Proof of an existing device permits ownership-preserving migration.
        body['legacy_token']=legacy['credentials']['service_token']
    raw=await request(session,'/oauth/device_authorization',body)
    if (not re.fullmatch('[A-Za-z0-9_-]{32,128}',str(raw.get('device_code','')))
        or not re.fullmatch('[A-Z2-9]{4}-[A-Z2-9]{4}',str(raw.get('user_code','')))
        or raw.get('verification_uri')!=ORIGIN+'/device'
        or raw.get('verification_uri_complete')!=ORIGIN+'/device#code='+raw.get('user_code','')
        or type(raw.get('expires_in')) is not int or not 60<=raw['expires_in']<=1800):
        raise LabServiceError('invalid_member_response')
    return {'device_code':raw['device_code'],'user_code':raw['user_code'],
            'url':raw['verification_uri_complete'],'verifier':verifier,
            'expires_at':time.time()+raw['expires_in'],'interval':max(5,min(int(raw.get('interval',5)),60)),
            'next_poll':0}


async def poll(session, grant):
    if time.time()>=grant['expires_at']:raise LabServiceError('expired_token')
    if time.time()<grant['next_poll']:raise LabServiceError('authorization_pending')
    grant['next_poll']=time.time()+grant['interval']
    try:
        raw=await request(session,'/oauth/token',{'client_id':CLIENT_ID,'grant_type':GRANT,
            'device_code':grant['device_code'],'code_verifier':grant['verifier']})
    except LabServiceError as exc:
        if exc.code=='slow_down':grant['interval']=min(60,grant['interval']+5)
        raise
    return valid_tokens(raw)


def state_from_tokens(tokens, previous=None):
    from .const import CONF_SERVICE_URL,CONF_SERVICE_TOKEN,CONF_SERVICE_CERT
    old=previous or {};values=old.get('credentials',{})
    old_scope=old.get('journal_scope')
    if not old_scope and values.get(CONF_SERVICE_URL) and values.get(CONF_SERVICE_TOKEN):
        old_scope=hashlib.sha256((values[CONF_SERVICE_URL]+'\0'+values[CONF_SERVICE_TOKEN]).encode()).hexdigest()[:24]
    # Keep a migrated device's endpoint/journal; new installations use public TLS.
    migrated=bool(previous and old.get('source') in ('operator','automatic','member'))
    url=values.get(CONF_SERVICE_URL,ORIGIN) if migrated else ORIGIN
    pin=values.get(CONF_SERVICE_CERT,'') if migrated else ''
    return {'version':1,'source':'member','enrolled':True,'device_id':tokens['device_id'],
            'credentials':{CONF_SERVICE_URL:url,CONF_SERVICE_TOKEN:tokens['access_token'],CONF_SERVICE_CERT:pin},
            'refresh_token':tokens['refresh_token'],'access_expires_at':time.time()+tokens['expires_in'],
            'journal_scope':old_scope if migrated else 'member-'+tokens['device_id'],
            'context_secret':old.get('context_secret') or (values.get(CONF_SERVICE_TOKEN) if migrated else None) or secrets.token_urlsafe(32)}
