import requests
import json
import os
import sys
import re
import random

from config import *

WB_CREATE_TIME = 'created_at'
WB_RAW_TEXT = 'raw_text'
WB_DEVICE = 'source'
WB_USER = 'user'
WB_TEXT = 'text'
WB_UNAME = 'screen_name'
WB_BLOG_TYPE = 'mblogtype'
WB_REPOSTS = 'reposts_count'
WB_COMMENTS = 'comments_count'
WB_ATTITUDES = 'attitudes_count'
WB_RETWEETED = 'retweeted_status'

U_DESCRIPTION = 'description'
U_VERIFIED = 'verified_reason'
U_NAME = WB_UNAME
U_IMG_URL = 'profile_image_url'
U_FOLLOWERS = 'followers_count'
U_FOLLOW = 'follow_count'

HF_TOTAL = 'total_number'
HF_USER = 'user'

HFC_COMMENTS = 'data'
HFC_LIKE_COUNT = 'like_count'
HFC_TINE = 'created_at'

CMT_TIME = 'created_at'
CMT_LIKE_COUNT = 'like_count'
CMT_TOTAL = 'total_number'
CMT_CMT = 'comments'

SCMT_TEXT = 'text'
SCMT_TIME = CMT_TIME
SCMT_USER = 'user'

TAB_PROFILE = 'profile'
TAB_WEIBO = 'weibo'
TAB_VIDEO = 'original_video'
TAB_ALBUM = 'album'

REQ_PROFILE = 0
REQ_WEIBO = 1

RESP_DICT = {
            403 : '[status]refused (403)',
            404 : '[status]not found s(404)',
            -1 : '[status]error! ({0})'
            }

API_HF_MID = '&mid={0}'
API_HFC_CID = '?cid={0}'
API_CID = '&containerid={0}'
API_PAGE = '&page={0}'
API_HF_ID = '?id={0}'

HOTFLOWCHILD_API = 'https://m.weibo.cn/comments/hotFlowChild{0}'  #0:cid
HOTFLOW_API = 'https://m.weibo.cn/comments/hotflow{0}{1}' #0:id 1:mid
WEIBO_API = 'https://m.weibo.cn/api/container/getIndex?type=uid&value={0}{1}{2}'  #0:uid 1:cid 2:sid

HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv,2.0.1) Gecko/20100101 Firefox/4.0.1'}

RE_TAG_COMPILE = re.compile('</?\w+[^>]*>') 


class IndexJsonAnalyzer:
    def __init__(self, json_dict :dict):
        self.__json_dict = json_dict

    
    @property
    def tabs(self) -> list:
        return self.__json_dict['data']['tabsInfo']['tabs']

    
    @property
    def data(self) -> dict:
        return self.__json_dict['data']

    
    @property
    def user_info(self) -> dict:
        return self.__json_dict['data']['userInfo']

    
    @property
    def user_image(self) -> list:
        '''
        返回一个代表图像的数组
        [[xxxxx],
         [xxxxx]]
        '''

        if not SHOW_USER_IMG:
            return [['(NO IMAGE)']]
        import imgutils

        #得到地址
        iurl = self.user_info[U_IMG_URL]
        print('[status]getting image...')
        r = requests.get(iurl, headers=HEADERS)
        check_response(r)
        print('[status]ok')

        #得到文件名称,先把条件去掉，再提取最后一个/分隔的元素
        fname = iurl.split('?')[0].split('/')[-1]
        fp = 'temp\\{0}'.format(fname)

        with open(fp, 'wb') as f:
            for chunk in r.iter_content(chunk_size=512):
                f.write(chunk)
        
        return imgutils.image_to_ascii(fp)
        

    def get_user_info_by_key(self, key :str) -> object:
        return self.user_info[key] if key in self.user_info else ''

    
    def get_containerid_by_key(self, tab_key):
        '''
        根据tab_key得到containerid
        如果找不到，则返回profile的containerid
        '''
        for tab in self.tabs:
            if tab['tabKey'] == tab_key:
                return tab['containerid']
        return self.tabs[0]['containerid']  #默认返回profile 项


class CardJsonAnalyzer:
    def __init__(self, json_dict :dict, eid :int):
        self.__json_dict = json_dict
        self.__eid = eid


    @property
    def eid(self) -> int:
        return self.__eid


    @property
    def json_dict(self) -> dict:
        return self.__json_dict


    @property
    def id(self) -> str:
        return self.__json_dict['mblog']['id']


    @property
    def __retweeted_json(self) -> dict:
        return self.__json_dict['mblog'][WB_RETWEETED] \
                if self.is_retweeted()  \
                else None


    def is_retweeted(self) -> bool:
        '''是否是转发评论的微博 (RT retweeted)'''
        return WB_RETWEETED in self.__json_dict['mblog']

    
    @property
    def retweeted(self):
        if not self.is_retweeted():
            return None
        #这里偷懒了，加了个mblog上去，为了适配make_weibo_str
        return CardJsonAnalyzer({'mblog':self.__json_dict['mblog'][WB_RETWEETED]}, 
                int(self.__retweeted_json['id'][-5:]))  #取后五位作id


class WeiboJsonAnalyzer:
    def __init__(self, json_dict :dict):
        self.__json_dict = json_dict
    

    @property
    def json(self) -> dict:
        return self.__json_dict
    
    @property
    def top(self) -> dict:
        return self.cards[0]


    @property
    def __data_cards(self) -> list:
        return self.__json_dict['data']['cards']


    @property
    def cards(self) -> list:
        return [CardJsonAnalyzer(self.__data_cards[eid], eid)
                    for eid in range(len(self.__data_cards))]


    def get_user(self, card :dict) -> dict:
        return card[WB_USER]


    def get_card_value(self, card :dict, key :str) -> object:
        '''由键得到卡片中某键值'''
        return card[key] if key in card else ''


    def get_card_by_id(self, _id :int) -> CardJsonAnalyzer:
        for c in self.cards:
            if int(c.id) == _id:
                return c
        return None


class WeiboPageManager:
    def __init__(self, first_page :WeiboJsonAnalyzer, user_info :IndexJsonAnalyzer):
        self.__page_stack = []
        self.__user_info = user_info
        self.__page = 1

        self.__page_stack.append(first_page)


    def __get_page(self) -> WeiboJsonAnalyzer:
        uid = self.__user_info.user_info['id']
        cid = self.__user_info.get_containerid_by_key('weibo')
        
        nxurl = WEIBO_API.format(uid, API_CID.format(cid), API_PAGE.format(self.__page))
        r = request_get(nxurl)
        
        ja = WeiboJsonAnalyzer(json.loads(r.text))
        
        self.__page_stack.append(ja)
        
        return ja


    def next_page(self) -> WeiboJsonAnalyzer:
        self.__page += 1
        
        return self.__get_page()

    
    def last_page(self) -> WeiboJsonAnalyzer:
        self.__page -= 1 if self.__page > 1 else 0

        return self.__get_page()


    def now_page(self) -> WeiboJsonAnalyzer:
        return self.__get_page()


class HotFlowJsonAnalyzer:
    def __init__(self, json_dict :dict):
        self.__json_dict = json_dict


    @property
    def __data_data(self) -> list:
        return self.__json_dict['data']['data']
    

    @property
    def comments(self) -> list:
        '''每次得到10个评论，返回一个CommentJsonAnalyzer列表'''
        return [CommentJsonAnalyzer(self.__data_data[eid], eid) 
                    for eid in range(len(self.__data_data))]


    @property
    def total(self) -> int:
        return self.__json_dict['data'][HF_TOTAL]


class CommentJsonAnalyzer:
    def __init__(self, json_dict :dict, eid :int):
        self.__json_dict = json_dict
        self.__eid = eid


    @property
    def eid(self) -> int:
        return self.__eid

    
    @property
    def like_count(self) -> int:
        return self.__json_dict[CMT_LIKE_COUNT]


    @property
    def create_time(self) -> str:
        return self.__json_dict[CMT_TIME]


    @property
    def total_number(self) -> int:
        return self.__json_dict[CMT_TOTAL]


    @property
    def id(self) -> int:
        return self.__json_dict['id']


    @property
    def text(self) -> str:
        return self.__json_dict['text']


    @property
    def user_info(self) -> dict:
        return self.__json_dict[HF_USER]


    @property
    def small_comments(self) -> list:
        if not self.__json_dict[CMT_CMT]:  #如果没有评论
            return []
        return self.__json_dict[CMT_CMT]


class HotFlowChildCommentJsonAnalyzer:
    def __init__(self, json_dict :dict, eid :int):
        self.__json_dict = json_dict
        self.__eid = eid


    @property
    def eid(self) -> int:
        return self.__eid

    
    @property
    def like_count(self) -> int:
        return self.__json_dict[HFC_LIKE_COUNT]


    @property
    def create_time(self) -> str:
        return self.__json_dict[HFC_TINE]


    @property
    def id(self) -> int:
        return self.__json_dict['id']


    @property
    def get_value_by_key(self, key :str) -> object:
        return self.__json_dict[key]    \
                if key in self.__json_dict   \
                else ''


    @property
    def text(self) -> str:
        return self.__json_dict['text']


class HotFlowChildJsonAnalyzer:
    def __init__(self, json_dict :dict):
        self.__json_dict = json_dict


    @property
    def json_dict(self) -> dict:
        return self.__json_dict


    @property
    def __data(self) -> list:
        return self.__json_dict['data']


    @property
    def comments(self) -> list:
        return [HotFlowChildCommentJsonAnalyzer(self.__data[eid], eid)
                    for eid in range(len(self.__data))]


def make_weibo_str(analyzer :WeiboJsonAnalyzer, card_obj :CardJsonAnalyzer):
    #检测是否是置顶微博
    #置顶微博没有raw_text,且blog type 是 2
    card = card_obj.json_dict['mblog']
    is_top = analyzer.get_card_value(card, WB_BLOG_TYPE) == 2
    
    wb_id = card_obj.eid
    wb_text = card[WB_RAW_TEXT] if WB_RAW_TEXT in card else card[WB_TEXT]
    wb_device = 'DEVICE:' + card[WB_DEVICE]
    wb_user = 'USER:' + card[WB_USER][WB_UNAME]
    wb_top = '置顶' if is_top else ''
    wb_time = card[WB_CREATE_TIME]
    wb_reposts = '📤 {0}'.format(card[WB_REPOSTS])
    wb_comment = '💬 {0}'.format(card[WB_COMMENTS])
    wb_attitude = '👍 {0}'.format(card[WB_ATTITUDES])

    #wb_text = replace_to_emoji(wb_text)

    ln1 = '  '.join((wb_user, wb_device, wb_top, wb_time)) + '\n'
    ln2 = clean_text(wb_text)
    ln3 = '\n' + ' | '.join((wb_reposts, wb_comment, wb_attitude))
    ln4 = 'ID : {0}'.format(wb_id)
    ln5 = ('RETWEET : \n' + '='*(os.get_terminal_size()[0]) + '\n' + (make_weibo_str(analyzer, card_obj.retweeted)[1:]) + '='*(os.get_terminal_size()[0])
                        ) if card_obj.is_retweeted() else ''

    return '\n' + ('-'*(os.get_terminal_size()[0] - len(ln4))) + ln4 + '\n'.join((ln1, ln2, ln3, ln5))


def make_user_profile_str(analyzer :IndexJsonAnalyzer):
    u_name = 'USER: ' + analyzer.user_info[U_NAME]
    u_desc = 'DESCRIBE: ' + analyzer.user_info[U_DESCRIPTION]
    u_verify = 'VERIFY: ' + analyzer.get_user_info_by_key(U_VERIFIED)
    u_img = analyzer.user_image
    u_follow = 'FOLLOW: ' + str(analyzer.user_info[U_FOLLOW])
    U_followers = 'FOLLOWERS: ' + str(analyzer.user_info[U_FOLLOWERS])

    ln1 = 'IMAGE:\n' + '\n'.join([''.join(ln) for ln in u_img])
    ln2 = u_name
    ln3 = u_verify
    ln4 = u_desc
    ln5 = ' | '.join((u_follow, U_followers))

    return '\n' + ('-'*os.get_terminal_size()[0]) + '\n'.join((ln1, ln2, ln5, ln3, ln4))


def make_hotflow_comment_str(analyzer :CommentJsonAnalyzer):
    cmt_id = analyzer.eid
    cmt_user = 'USER : ' + analyzer.user_info[U_NAME]
    cmt_text = '\n' + analyzer.text
    cmt_scmt = '\n'.join([s[SCMT_USER][U_NAME] + ' : '  + clean_text(s[SCMT_TEXT]) \
                            for s in analyzer.small_comments])
    cmt_time = 'TIME : ' + analyzer.create_time

    ln1 = '  '.join((cmt_user, cmt_time))
    ln2 = clean_text(cmt_text)
    ln3 = '\n' + cmt_scmt
    ln4 = 'ID : {0}'.format(cmt_id)

    return '\n' + ('~'*(os.get_terminal_size()[0] - len(ln4)) + ln4 + '\n'.join((ln1, ln2, ln3)))


def replace_to_emoji(text :str):
    '''讲博文中的表情文本(如[doge])替换成emoji'''
    return text.replace('[doge]', '🐶')


def clean_text(text :str) -> str:
    '''除去文本里的HTML标签'''
    return RE_TAG_COMPILE.sub('', text)


def request_get_index(uesr_id :int) -> requests.Response:
    '''
    如果响应200，则返回Response对象
    '''
    print('[status]requesting...')
    r = requests.get(WEIBO_API.format(uesr_id, '', ''))

    if r.status_code != 200:
        print(RESP_DICT.get(r.status_code, RESP_DICT[-1].format(r.status_code)))
        sys.exit(1)
    print('[status]ok')

    return r


def request_get(url :str, msg='requesting...') -> requests.Response:
    print('[status]{0}'.format(msg))
    r = requests.get(url)

    if r.status_code != 200:
        print(RESP_DICT.get(r.status_code, RESP_DICT[-1].format(r.status_code)))
        sys.exit(1)
    print('[status]ok')
    return r


def check_response(r :requests.Response):
    if r.status_code != 200:
        print(RESP_DICT.get(r.status_code, RESP_DICT[-1].format(r.status_code)))
        sys.exit(1)


def get_first_page(uid :int, u_analyzer :IndexJsonAnalyzer):
    cid = u_analyzer.get_containerid_by_key('weibo')
    uid = str(uid)

    url = WEIBO_API.format(uid, API_CID.format(cid), '')  #不需要 since_id
    r = request_get(url)

    return WeiboJsonAnalyzer(json.loads(r.text))


def get_hotflow_child(cid :int) -> HotFlowChildJsonAnalyzer:
    '''cid : 该评论的cid'''
    url = HOTFLOWCHILD_API.format(API_HFC_CID.format(cid))
    r = request_get(url, 'getting hotflow child...')

    return HotFlowChildJsonAnalyzer(json.loads(r.text))


def get_hotflow(_id :int, mid :int) -> HotFlowJsonAnalyzer:
    url = HOTFLOW_API.format(API_HF_ID.format(_id), API_HF_MID.format(mid))
    r = request_get(url, 'getting hotflow...')

    return HotFlowJsonAnalyzer(json.loads(r.text))


def show_all_weibo(mgr :WeiboPageManager):
    wja = mgr.now_page()

    for c in wja.cards:
        print(make_weibo_str(wja, c))


if __name__ == '__main__':
    uid_nezha = '6217939256'
    uid = uid_nezha

    if len(sys.argv) > 2 and sys.argv[-2] == '-u':
        uid = int(sys.argv[-1])
    
    rindex = request_get_index(uid)
    ua = IndexJsonAnalyzer(json.loads(rindex.text))
    wa = get_first_page(uid, ua)

    
    show_all_weibo(WeiboPageManager(wa, ua))
    '''
    
    
    pgm = WeiboPageManager(get_first_page(uid, ua), ua)
    wa = pgm.now_page()

    hfc = get_hotflow(4412386138119333, '4412386138119333')

    for c in hfc.comments:
        s = make_hotflow_comment_str(c)
        print(s)
    
    
    for c in wa.cards:
        print(make_weibo_str(wa, c))
        print('\n')'''
