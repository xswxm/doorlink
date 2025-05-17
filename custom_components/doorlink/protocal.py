
SIP_VERSION = '2.0'
USER_AGENT = 'DnakeVoip v1.0'

class CSeq:
    REGISTER = 1
    OPTION = 20
    EVENT = 20
    MESSAGE = 20
    BYE = 21

class METHOD:
    # INVITE = 'INVITE'
    # ACK = 'ACK'
    # CANCEL = 'CANCEL'
    # OPTIONS = 'OPTIONS'
    # BYE = 'BYE'
    # REFER = 'REFER'
    # NOTIFY = 'NOTIFY'
    MESSAGE = 'MESSAGE'
    # SUBSCRIBE = 'SUBSCRIBE'
    # INFO = 'INFO'
    REGISTER = 'REGISTER'
    BYE = 'BYE'

class PARAMS:
    PARAMS = 'params'
    EVENT_URL = 'event_url'
    TO = 'to'
    ELEV = 'elev'
    DIRECT = 'direct'
    BUILD = 'build'
    UNIT = 'unit'
    FLOOR = 'floor'
    FAMILY = 'family'
    APP = 'app'
    EVENT = 'event'
    HOST = 'host'
    ID = 'id'
    IDX = 'idx'
    VERSION = 'version'
    PROXY_URL = 'proxy_url'
    PROXY_OK = 'proxy_ok'

class EVENT:
    APPOINT = 'appoint'
    UNLOCK = 'unlock'
    PERMIT = 'permit'

class EVENT_URL:
    JOIN = '/elev/join'
    APPOINY = '/elev/appoint'
    UNLOCK = '/talk/unlock'
    PERMIT = '/elev/permit'
    HEARTBEAT = '/msg/hearbeat'

class APP:
    ELEV = 'elev'
    TALK = 'talk'

class SIP_HEADER:
    def MESSAGE(src_id, src_ip, src_port, dst_id, dst_ip, dst_port, branch, tag, call_id, body_length):
        return {
            "Via" : f"SIP/{SIP_VERSION}/UDP {src_ip}:{src_port};rport;branch={branch}",
            "From" : f"<sip:{src_id}@{src_ip}:{src_port}>;tag={tag}",
            "To" : f"<sip:{dst_id}@{dst_ip}:{dst_port}>",
            "Call-ID" : call_id,
            "CSeq" : f"{CSeq.MESSAGE} {METHOD.MESSAGE}",
            "Content-Type" : "text/plain",
            "Max-Forwards" : 70,
            "User-Agent" : USER_AGENT,
            "Content-Length" : body_length
        }
    def BYE(src_id, src_ip, src_port, dst_id, dst_ip, dst_port, branch, tag_from, tag_to, call_id, body_length = 0):
        return {
            "Via" : f"SIP/{SIP_VERSION}/UDP {src_ip}:{src_port};rport;branch={branch}",
            "From" : f"<sip:{src_id}@{src_ip}:{src_port}>;tag={tag_from}",
            "To" : f"<sip:{dst_id}@{dst_ip}:{dst_port}>;tag={tag_to}",
            "Call-ID" : call_id,
            "CSeq" : f"{CSeq.BYE} {METHOD.BYE}",
            "Contact": f"<sip:{src_id}@{src_ip}:{src_port}>",
            "Max-Forwards": 70,
            "User-Agent" : USER_AGENT,
            "Content-Length" : body_length
        }
    def REGISTER(cseq, src_id, src_ip, src_port, dst_ip, branch, tag, call_id, line, auth = None, body_length = 0):
        header = {
            "Via" : f"SIP/{SIP_VERSION}/UDP {src_ip}:{src_port};rport;branch={branch}",
            "From" : f"<sip:{src_id}@{dst_ip}>;tag={tag}",
            "To" : f"<sip:{src_id}@{dst_ip}>",
            "Call-ID" : call_id,
            "CSeq" : f"{cseq} {METHOD.REGISTER}",
            "Contact": f"<sip:{src_id}@{src_ip}:{src_port};line={line}>",
            "Allow": "INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, NOTIFY, MESSAGE, SUBSCRIBE, INFO",
            "Max-Forwards" : 70,
            "User-Agent" : USER_AGENT,
            "Expires": 3600,
            "Content-Length" : body_length
        }
        if auth:
            header['Proxy-Authorization'] = auth
        return header
        # Proxy-Authorization: Digest username="16013301", realm="192.168.1.222", nonce="13376505302:3f2dc133cd3369487f249b1aa8d6e569", uri="sip:172.16.0.2", response="e3fbbcc8c07a4f7be4597f5190827cec", algorithm=MD5, cnonce="0a4f113b", qop=auth, nc=00000001


class SIP_LINE:
    def MESSAGE(dst_id, dst_ip, dst_port):
        return f'{METHOD.MESSAGE} sip:{dst_id}@{dst_ip}:{dst_port} SIP/{SIP_VERSION}'

    def BYE(dst_id, dst_ip, dst_port):
        return f'{METHOD.BYE} sip:{dst_id}@{dst_ip}:{dst_port} SIP/{SIP_VERSION}'

    def REGISTER(dst_ip):
        return f'{METHOD.REGISTER} sip:{dst_ip} SIP/{SIP_VERSION}'

class SIP_BODY:
    def JOIN(): 
        return {
            PARAMS.EVENT_URL: EVENT_URL.JOIN
        }
    def APPOINT(dst_id, dst_ip, dst_port, elev, direct, build, unit, floor, family):
        return {
            PARAMS.TO: f'sip:{dst_id}@{dst_ip}:{dst_port}',  # 16019901@172.16.1.161:5060
            PARAMS.ELEV: elev,
            PARAMS.DIRECT: direct,
            PARAMS.BUILD: build,
            PARAMS.UNIT: unit,
            PARAMS.FLOOR: floor,
            PARAMS.FAMILY: family,
            PARAMS.APP: APP.ELEV,
            PARAMS.EVENT: EVENT.APPOINT,
            PARAMS.EVENT_URL: EVENT_URL.APPOINY
        }
    def UNLOCK(src_id, build, unit, floor, family):
        return {
            PARAMS.APP: APP.TALK,
            PARAMS.EVENT: EVENT.UNLOCK,
            PARAMS.EVENT_URL: EVENT_URL.UNLOCK,
            PARAMS.HOST: src_id,
            PARAMS.BUILD: build,
            PARAMS.UNIT: unit,
            PARAMS.FLOOR: floor,
            PARAMS.FAMILY: family
        }
    def PERMIT(dst_id, dst_ip, dst_port, elev, build, unit, floor, family):
        return {
            PARAMS.APP: APP.ELEV,
            PARAMS.EVENT: EVENT.PERMIT,
            PARAMS.EVENT_URL: EVENT_URL.PERMIT,
            PARAMS.TO: f'sip:{dst_id}@{dst_ip}:{dst_port}',
            PARAMS.ELEV: elev,
            PARAMS.BUILD: build,
            PARAMS.UNIT: unit,
            PARAMS.FLOOR: floor,
            PARAMS.FAMILY: family
        }
    def HEARTBEAT(id, idx, proxy_url, proxy_ok):
        return {
            PARAMS.EVENT_URL: EVENT_URL.HEARTBEAT,
            PARAMS.ID: id,
            PARAMS.IDX: idx,
            PARAMS.VERSION: 1,
            PARAMS.PROXY_URL: proxy_url,
            PARAMS.PROXY_OK: proxy_ok
        }
