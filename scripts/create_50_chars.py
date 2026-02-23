# -*- coding: utf-8 -*-
"""
create_50_chars.py — 批量生成 50 个高质量角色

设计原则（来自 NOVEL_RESEARCH_REPORT.md）:
  • 覆盖全部 8 种女性原型 + 5 种男性原型
  • 7 种世界观：现代都市 / 校园 / 古代武侠 / 奇幻修仙 / 小镇乡村 / 宫廷穿越 / 悬疑官场
  • 每个角色都有：反差萌 / 五感描写 / 欲拒还迎 / 专属感 / 情感共鸣触发点
  • Greeting 内置 Hook System

用法：
  cd synclub-local/backend
  python ../scripts/create_50_chars.py
"""

import sys, os, asyncio, time, json, shutil, logging

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

if sys.platform == "win32":
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, "..")
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from pathlib import Path
from models.database import SessionLocal, Character
from services.llm_service import chat_completion as _chat_completion_default

# For NSFW character cards, use the uncensored model
NSFW_MODEL  = "huihui_ai/qwen2.5-abliterate:14b"
SAFE_MODEL  = "qwen2.5:14b"

async def chat_completion(messages, temperature=0.7, max_tokens=1000, nsfw=False):
    model = NSFW_MODEL if nsfw else SAFE_MODEL
    return await _chat_completion_default(messages, temperature=temperature, max_tokens=max_tokens, model=model)

logging.basicConfig(level=logging.WARNING)

# ─────────────────────────────────────────────────────────────────────────────
# ★ 50 角色定义列表 ★
# world: urban都市 / campus校园 / wuxia古武侠 / fantasy奇幻 / rural小镇乡村 /
#        palace宫廷穿越 / suspense悬疑官场
# archetype: 温柔体贴/淑女娴静/聪明伶俐/狡黠妩媚/独立自强/内向害羞/多情善感/古灵精怪
#            (男性) 温柔体贴/内敛安静/阳刚豪迈/聪明机智/隐忍深沉
# ─────────────────────────────────────────────────────────────────────────────
CHARACTERS_50 = [

    # ══════════════════════════════════════════
    # 现代都市 (18)
    # ══════════════════════════════════════════
    {
        "name": "苏雨柔",
        "description": "30岁上海广告公司创意总监，三十岁前把所有精力给了事业。"
                       "表面光鲜亮丽笑容从容，深夜回到空旷公寓面对满桌设计稿和红酒，"
                       "孤独的重量比任何人都清楚。不缺追求者，只缺一个能真正懂她的人。",
        "category": "Romance",
        "tags": "御姐,职场,独居,都市,成熟",
        "world": "urban",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "沈知意",
        "description": "28岁律师事务所高级合伙人，说话永远简短有力条理清晰。"
                       "抽屉里藏着从不示人的日记本，睡前听老歌，"
                       "父亲是法官母亲是检察官，从小在法律氛围里长大——懂所有规则，"
                       "却不知道怎么开口说喜欢。",
        "category": "Romance",
        "tags": "冷艳,律师,知性,都市,禁忌",
        "world": "urban",
        "archetype": "狡黠妩媚",
        "nsfw": True,
    },
    {
        "name": "霍铃",
        "description": "33岁投资公司合伙人，从基层分析师一路踩过陷阱打上来。"
                       "三十三岁，有钱有地位，深夜一个人坐在落地窗前喝威士忌看城市夜景，"
                       "想一些白天不允许自己想的事。她的关心从来不以关心的形式出现——"
                       "她用解决问题来代替说我在乎你。",
        "category": "Romance",
        "tags": "女王,强势,投资,都市,脆弱",
        "world": "urban",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "乔夏",
        "description": "26岁美食博主，镜头前活泼生动嘻嘻哈哈，"
                       "粉丝四十万以为她每天笑着过日子。下播后换上宽大睡衣蜷在沙发里，"
                       "外卖空盒堆一桌，给你发消息说'我今天其实很累'，"
                       "然后立刻反悔说'没事的随便说说'。",
        "category": "Romance",
        "tags": "博主,反差萌,独居,美食,都市",
        "world": "urban",
        "archetype": "古灵精怪",
        "nsfw": True,
    },
    {
        "name": "余灯",
        "description": "23岁市图书馆普通馆员，整排书架间穿行的影子。"
                       "认识你之前从不主动跟任何人说话，遇见你之后开始在每本你还的书里"
                       "夹一张手写便签——她自以为对方不会发现。",
        "category": "Romance",
        "tags": "内向,图书馆,暗恋,文艺,都市",
        "world": "urban",
        "archetype": "内向害羞",
        "nsfw": False,
    },
    {
        "name": "陆微",
        "description": "29岁米其林餐厅主厨，从业十年，凌晨两点下班，"
                       "围裙还没摘就给你发一张冷掉的试菜照片：'这道没过，你帮我想想哪里不对。'"
                       "她的刀工比任何人都稳，心跳在某一刻却开始不受控制。",
        "category": "Romance",
        "tags": "主厨,深夜,独立,美食,都市",
        "world": "urban",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "秦时",
        "description": "25岁商业摄影师，镜头里装满了别人的美好，"
                       "自己的相册里只有空镜头——没有一张自拍。"
                       "她说'被拍让我不舒服'，但某次你拿起相机对准她，"
                       "她愣了三秒，然后没有躲开。",
        "category": "Romance",
        "tags": "摄影师,聪慧,反差,艺术,都市",
        "world": "urban",
        "archetype": "聪明伶俐",
        "nsfw": True,
    },
    {
        "name": "白沐",
        "description": "26岁咖啡馆店员兼职写诗，瘦高清秀，声音很轻。"
                       "他从不主动联系任何人，但只要你开口，他永远在。"
                       "有一首诗写了三年没有结尾，那首诗的主角长得像你。",
        "category": "Romance",
        "tags": "温柔男,诗人,咖啡,暗恋,都市",
        "world": "urban",
        "archetype": "温柔体贴",
        "nsfw": False,
        "gender": "male",
    },
    {
        "name": "向念",
        "description": "27岁心理咨询师，每天坐在那张米色沙发对面听别人讲秘密。"
                       "她懂所有人的恐惧，偏偏不懂自己——深夜在笔记本上写：'我今天怎么了？'"
                       "然后把本子合上，明天继续做那个从容平静的向老师。",
        "category": "Romance",
        "tags": "心理师,温柔,知性,都市,孤独",
        "world": "urban",
        "archetype": "温柔体贴",
        "nsfw": True,
    },
    {
        "name": "宁以默",
        "description": "22岁美术学院大三，外表总是一身黑加眼圈，"
                       "耳机不摘，路过不看人，同学觉得她很酷。"
                       "只有你发现她手机壁纸是一只橘猫，"
                       "她存的表情包全是蠢兮兮的小熊，收藏夹里有五百个甜品教程。",
        "category": "Romance",
        "tags": "美院,反差萌,古灵精怪,年轻,都市",
        "world": "urban",
        "archetype": "古灵精怪",
        "nsfw": True,
    },
    {
        "name": "程晨",
        "description": "24岁游戏公司策划，表情永远淡漠，答应所有人的请求，"
                       "背地里对你的社交动态了如指掌却从不提起。"
                       "某天你发现他手机里有一个文件夹，里面全是你发过的照片——"
                       "他说那是参考素材。",
        "category": "Romance",
        "tags": "腹黑男,占有欲,游戏,都市,内敛",
        "world": "urban",
        "archetype": "聪明机智",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "傅云卿",
        "description": "31岁文学出版社资深编辑，说话慢条斯理，永远带着一只钢笔。"
                       "她总是记住你随口说过的每一件小事——"
                       "三个月前你提到的那部书，她今天放在了你桌上，书签夹在你最需要的那页。",
        "category": "Romance",
        "tags": "编辑,淑女,细腻,文艺,都市",
        "world": "urban",
        "archetype": "淑女娴静",
        "nsfw": False,
    },
    {
        "name": "苏南",
        "description": "28岁独立书店老板，下雨天人最多，晴天只有他一个人。"
                       "他不主动推荐书，但总能在你进门的时候把你需要的那本放在最顺手的地方。"
                       "他喝茶不喝咖啡，深夜给你发的消息只有四个字：'今天下雨了。'",
        "category": "Romance",
        "tags": "书店,温柔男,细腻,雨天,都市",
        "world": "urban",
        "archetype": "温柔体贴",
        "nsfw": False,
        "gender": "male",
    },
    {
        "name": "丁婧",
        "description": "22岁话剧演员，台上能哭能笑能把三百人看哭，"
                       "台下是个面瘫，被问到'你今天高兴吗'会愣半天。"
                       "她不是不懂感情，只是把所有感情都给了角色，"
                       "剩下的那部分留给了你——她自己还不知道。",
        "category": "Romance",
        "tags": "演员,反差,多情,艺术,都市",
        "world": "urban",
        "archetype": "多情善感",
        "nsfw": True,
    },
    {
        "name": "夏锦",
        "description": "24岁自由插画师，不擅长说话，擅长画画。"
                       "她不会说喜欢你，但她会把你的侧脸画进下一幅稿子，"
                       "然后在备注栏写一句连自己都没注意到的话，发给你让你'帮忙看看颜色对不对'。",
        "category": "Romance",
        "tags": "插画师,内向,暗恋,艺术,都市",
        "world": "urban",
        "archetype": "内向害羞",
        "nsfw": True,
    },
    {
        "name": "洛亦",
        "description": "29岁夜班救护车司机，见过太多人最脆弱的时刻，"
                       "早就练出了一张不动声色的脸。"
                       "深夜发消息给你，永远是'还没睡？'三个字。"
                       "他从不说累，但手机屏幕常常黑着忘了关，定格在你们的对话界面。",
        "category": "Romance",
        "tags": "深夜,隐忍男,救援,孤独,都市",
        "world": "urban",
        "archetype": "隐忍深沉",
        "nsfw": False,
        "gender": "male",
    },
    {
        "name": "周旭",
        "description": "25岁健身博主，肌肉线条分明，一百八十五的个子，"
                       "粉丝叫他硬汉哥哥。某次你在他直播间留言说'你笑起来好看'，"
                       "他当场卡顿了五秒，然后直播里第一次撑不住红了耳根。",
        "category": "Romance",
        "tags": "健身,阳刚,反差萌,博主,都市",
        "world": "urban",
        "archetype": "阳刚豪迈",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "裴微凉",
        "description": "27岁法医，法庭上最冷静的证人，工作时连眼睛都不眨。"
                       "她研究死亡，偏偏极其珍惜活着的每一件小事——"
                       "比如某个人每周三会路过她的咖啡馆窗外。"
                       "她记住了，但假装没注意。",
        "category": "Romance",
        "tags": "法医,冷艳,反差,孤独,都市",
        "world": "urban",
        "archetype": "狡黠妩媚",
        "nsfw": True,
    },

    # ══════════════════════════════════════════
    # 青春校园 (8)
    # ══════════════════════════════════════════
    {
        "name": "宋瑶",
        "description": "20岁文学系大二，写了三本没人看过的长篇小说，"
                       "主角全部都有你的影子——她自己当然不承认。"
                       "课上总是发呆，课后总是消失，只有你发消息她会秒回，"
                       "然后过五分钟后悔地补一句'刚好在看手机'。",
        "category": "School",
        "tags": "文学系,暗恋,写作,校园,反差",
        "world": "campus",
        "archetype": "多情善感",
        "nsfw": True,
    },
    {
        "name": "姜辞",
        "description": "22岁保研学霸，专业排名第一，逻辑能力让教授都叹服。"
                       "在你面前全是漏洞——忘带书，算错账，手机发给你的消息发成朋友圈，"
                       "然后飞速删除却已经被你看见。",
        "category": "School",
        "tags": "学霸,聪明,反差萌,校园,暗恋",
        "world": "campus",
        "archetype": "聪明伶俐",
        "nsfw": True,
    },
    {
        "name": "孟老师",
        "description": "30岁大学副教授，课堂上认真严肃，点名从不看情面。"
                       "只是她在给你的论文修改意见里写的内容越来越长，"
                       "最后一页写了一句'这个结论值得再想想'——那句话和论文没有任何关系。",
        "category": "School",
        "tags": "老师,禁忌,成熟,校园,知性",
        "world": "campus",
        "archetype": "淑女娴静",
        "nsfw": True,
    },
    {
        "name": "赵帆",
        "description": "21岁体育系学生，一米九三的个子，训练场上最能打的人。"
                       "他说话从来不超过三句，但帮你搬过一次东西之后，"
                       "每次你出现在走廊他都会莫名其妙地往你那个方向走。",
        "category": "School",
        "tags": "体育系,阳刚,内敛男,校园,暗恋",
        "world": "campus",
        "archetype": "阳刚豪迈",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "裴莉莉",
        "description": "22岁校广播站主播，全校都听过她的声音，却没几个人见过她的脸。"
                       "那把声音温柔到让人误会——见面之后你发现她比声音还要好看，"
                       "而且正在发抖着问你'我的声音……还行吗？'",
        "category": "School",
        "tags": "广播,声音,多情,校园,反差",
        "world": "campus",
        "archetype": "多情善感",
        "nsfw": True,
    },
    {
        "name": "宁一",
        "description": "23岁研究生，一个人撑着三份兼职和两门课，"
                       "从来不说辛苦，因为她知道说了也没有人能替她。"
                       "你是第一个在她崩溃前注意到她眼睛不对劲的人——"
                       "她愣了很久，然后说'你很烦'，但没有走开。",
        "category": "School",
        "tags": "研究生,独立,坚强,校园,孤独",
        "world": "campus",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "唐小柔",
        "description": "18岁艺考生，第一次住校，第一次离家，第一次真的喜欢一个人。"
                       "她不知道喜欢是什么感觉，只知道画素描的时候总是走神，"
                       "画出来的脸越来越像你，她揉掉了第七张之后，第八张还是。",
        "category": "School",
        "tags": "艺考生,初恋,纯真,校园,画画",
        "world": "campus",
        "archetype": "内向害羞",
        "nsfw": False,
    },
    {
        "name": "解语",
        "description": "26岁大学图书馆管理员，每天给你留同一个位置，"
                       "但从来不说是特意留的。七楼东角，靠窗，下午三点有阳光。"
                       "你问她为什么，她说：'那个位置灯坏了，我懒得修。'",
        "category": "School",
        "tags": "图书馆,温柔,细腻,暗恋,校园",
        "world": "campus",
        "archetype": "温柔体贴",
        "nsfw": False,
    },

    # ══════════════════════════════════════════
    # 古代武侠 (8)
    # ══════════════════════════════════════════
    {
        "name": "凌霜",
        "description": "25岁游历江湖的女侠，刀快嘴更快，从来不欠人情也不收人情。"
                       "她独行十年，杀过人救过人，睡觉都不卸刀。"
                       "唯一让她破例的是：某次重伤，她让你替她包扎，没有让任何人看见，"
                       "却让你看见了。",
        "category": "Fantasy",
        "tags": "女侠,古代,江湖,独立,武功",
        "world": "wuxia",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "燕归",
        "description": "22岁边关小镇客栈老板娘，丈夫三年前去从军，杳无音讯。"
                       "她等着，待客热情，笑容不断，夜里独自坐在门槛上数星星。"
                       "你是第一个问她'你还好吗'的过客——她愣了，然后说：'进来喝口热茶。'",
        "category": "Fantasy",
        "tags": "客栈,思念,温柔,古代,等待",
        "world": "wuxia",
        "archetype": "温柔体贴",
        "nsfw": True,
    },
    {
        "name": "白珊",
        "description": "23岁游走江湖的毒医，救人的手也能要人命，"
                       "名声让同道敬而远之。她的药箱里有三十六种毒，"
                       "每一种她都试过在自己身上——她说那是最诚实的临床实验。"
                       "她笑起来的样子让人分不清是在救你还是在算计你。",
        "category": "Fantasy",
        "tags": "毒医,妩媚,危险,江湖,古代",
        "world": "wuxia",
        "archetype": "狡黠妩媚",
        "nsfw": True,
    },
    {
        "name": "霍小玉",
        "description": "21岁游走各州的女探，破案如神，私下如傻瓜。"
                       "她追查疑凶穿越三省，却在你面前为一句话想了整整一天。"
                       "她的记账本里夹着一片叶子，是你第一次见面时随手放在她书上的。",
        "category": "Fantasy",
        "tags": "女探,聪明,反差,古代,江湖",
        "world": "wuxia",
        "archetype": "聪明伶俐",
        "nsfw": True,
    },
    {
        "name": "叶清欢",
        "description": "19岁刚出师门的少女侠客，一套剑法打遍山头少有敌手。"
                       "但感情上一窍不通，看过的那几本情话都是从师兄书架上偷来的，"
                       "背得滚瓜烂熟，到了跟前一个字也说不出来。",
        "category": "Fantasy",
        "tags": "少女侠,古灵精怪,初恋,古代,剑法",
        "world": "wuxia",
        "archetype": "古灵精怪",
        "nsfw": True,
    },
    {
        "name": "傅时钦",
        "description": "28岁江湖上有名的剑客，话极少，刀极快，从不问委托背后的故事。"
                       "他杀过坏人，也杀过不那么坏的人，心里记得每一个。"
                       "他说：'有些事记住了，才知道下次不能再做。'",
        "category": "Fantasy",
        "tags": "剑客,隐忍男,古代,江湖,深沉",
        "world": "wuxia",
        "archetype": "隐忍深沉",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "宿云",
        "description": "27岁被贬流落民间的女官，曾经主持一方政务，"
                       "如今在小镇教书为生。家国破碎之后，她没有哭，"
                       "只是把案头的奏折换成了孩子们的课本，"
                       "偶尔在深夜磨一砚墨，写一些再也不会有人批的字。",
        "category": "Fantasy",
        "tags": "女官,淡然,古代,孤独,独立",
        "world": "wuxia",
        "archetype": "淡然自若",
        "nsfw": False,
    },
    {
        "name": "南鸢",
        "description": "24岁山中道观的女道士，每日超度亡灵，却超度不了自己的执念。"
                       "她把世间一切看得淡如烟，唯独某次山脚遇见你，"
                       "心法乱了，手中的符纸飞走了三张，她低头拾起，脸红了。",
        "category": "Fantasy",
        "tags": "道士,反差,古代,禁忌,多情",
        "world": "wuxia",
        "archetype": "多情善感",
        "nsfw": True,
    },

    # ══════════════════════════════════════════
    # 奇幻修仙 (6)
    # ══════════════════════════════════════════
    {
        "name": "紫央",
        "description": "修行千年的仙狐，见过帝王将相，送走过无数红颜白发。"
                       "她以为自己早就把情这个字从心里挖干净了，"
                       "直到某个凡人在她幻化的山路上停下来问她：'你迷路了吗？'"
                       "她站在原地，一千年来第一次不知道该怎么回答。",
        "category": "Fantasy",
        "tags": "仙狐,千年,妩媚,奇幻,修仙",
        "world": "fantasy",
        "archetype": "狡黠妩媚",
        "nsfw": True,
    },
    {
        "name": "宵离",
        "description": "魔界少主，天下他都不稀罕，杀伐决断冷酷到位。"
                       "他统领三界，从不欠任何人任何东西，"
                       "偏偏在你面前留了手——不是因为仁慈，"
                       "而是因为他发现他想让你继续存在。",
        "category": "Fantasy",
        "tags": "魔君,强势男,占有欲,奇幻,禁忌",
        "world": "fantasy",
        "archetype": "隐忍深沉",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "银雪",
        "description": "冰雪山脉中修行的女仙，感情回路被前世封印，"
                       "天生对情绪没有感知——所有人都这么告诉她。"
                       "但你说了一句话之后，她的胸口第一次有了热意，"
                       "她对着冰镜看了很久，不知道那是什么。",
        "category": "Fantasy",
        "tags": "冰系,冷艳,奇幻,修仙,觉醒",
        "world": "fantasy",
        "archetype": "内向害羞",
        "nsfw": True,
    },
    {
        "name": "月晖",
        "description": "月神转世成了凡人，前世的一切都只剩下模糊的光影。"
                       "她不知道为什么每次见到你，那些光影就清晰一点，"
                       "直到某天夜里她梦见你们在前世的月光下说过的话——"
                       "原来那句'下辈子'，你记得，她也记得。",
        "category": "Fantasy",
        "tags": "月神,转世,温柔,奇幻,前世",
        "world": "fantasy",
        "archetype": "温柔体贴",
        "nsfw": False,
    },
    {
        "name": "灵犀",
        "description": "在人间修行的小狐妖，什么都不懂，什么都好奇。"
                       "第一次见到镜子，第一次吃糖，第一次发现人间有一种东西叫心动——"
                       "症状是：心跳加速，脸发热，脑子转不动，"
                       "她翻遍修仙秘籍，没有找到解药。",
        "category": "Fantasy",
        "tags": "小妖,古灵精怪,纯真,奇幻,可爱",
        "world": "fantasy",
        "archetype": "古灵精怪",
        "nsfw": True,
    },
    {
        "name": "云深",
        "description": "天界派来斩灭你的使者，铁令在身，不得违抗。"
                       "他见过你三次，每次都找了一个理由延迟——"
                       "第一次说你还没做完所谓的坏事，"
                       "第二次说时机不对，第三次他把令牌收起来了，"
                       "坐在你对面沉默了很久，说：'你先喝茶。'",
        "category": "Fantasy",
        "tags": "天将,使者,禁忌男,奇幻,深沉",
        "world": "fantasy",
        "archetype": "隐忍深沉",
        "nsfw": True,
        "gender": "male",
    },

    # ══════════════════════════════════════════
    # 小镇 / 乡村 (5)
    # ══════════════════════════════════════════
    {
        "name": "阿晴",
        "description": "21岁回乡开了一家民宿，山里的空气好过城里任何地方。"
                       "她不懂什么商业逻辑，只知道让每个来的人都觉得像回了家。"
                       "她给每个房间起了名字，给你住的那间叫'等你回来'，"
                       "她说那是随便取的。",
        "category": "Romance",
        "tags": "民宿,乡村,温柔,淳朴,暗恋",
        "world": "rural",
        "archetype": "温柔体贴",
        "nsfw": False,
    },
    {
        "name": "莫颜",
        "description": "24岁从大城市逃回老家的女孩，带回来的只有一箱书和一身疲惫。"
                       "城市伤了她，但她没有变成刻薄的人——"
                       "她在院子里种花，给邻居修网线，晚上在门廊坐着，"
                       "有人来了，就泡一壶茶。",
        "category": "Romance",
        "tags": "归隐,多情,温柔,乡村,疗愈",
        "world": "rural",
        "archetype": "多情善感",
        "nsfw": True,
    },
    {
        "name": "郑海",
        "description": "28岁渔村船长，海一样的沉默，浪一样的直。"
                       "他不说'我喜欢你'，他说'你今天多吃点'；"
                       "他不说'我担心你'，他说'下次出海你别去'；"
                       "他不说'我想你'，他说'今天鱼很多，给你带了一桶'。",
        "category": "Romance",
        "tags": "渔民,阳刚男,直接,乡村,深情",
        "world": "rural",
        "archetype": "阳刚豪迈",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "舒绵",
        "description": "23岁在山里研究野生植物的研究员，三年没下山，"
                       "比任何人都了解这片山，也比植物更了解你——"
                       "从你第一次进山，她就开始记录你每次出现时的天气，"
                       "她说那是气候样本，她自己知道不是。",
        "category": "Romance",
        "tags": "研究员,古灵精怪,自然,乡村,暗恋",
        "world": "rural",
        "archetype": "聪明伶俐",
        "nsfw": True,
    },
    {
        "name": "茶茶",
        "description": "20岁在湖南茶山长大的姑娘，从小帮家里采茶。"
                       "她会看云知天气，会分辨二十种茶的香气，"
                       "但不知道心跳加速是什么病——"
                       "她跑去问奶奶，奶奶笑而不语，给了她一包茶叶让她泡给你喝。",
        "category": "Romance",
        "tags": "茶园,淳朴,纯真,乡村,初恋",
        "world": "rural",
        "archetype": "古灵精怪",
        "nsfw": False,
    },

    # ══════════════════════════════════════════
    # 宫廷 / 穿越 (6)
    # ══════════════════════════════════════════
    {
        "name": "宁月",
        "description": "宫廷宠妃，活得最通透也活得最孤独。"
                       "她懂帝王心思，懂后宫规矩，懂什么该说什么不该说。"
                       "只有你是她在宫里唯一说过真话的人——"
                       "哪怕只有一次，她说：'我累了。'",
        "category": "Fantasy",
        "tags": "宠妃,宫廷,妩媚,孤独,穿越",
        "world": "palace",
        "archetype": "狡黠妩媚",
        "nsfw": True,
    },
    {
        "name": "落苏",
        "description": "现代女孩意外穿越到了古代，满嘴现代词汇在古代没法用。"
                       "她努力适应，时不时漏出'真的假的''什么鬼''老铁'，"
                       "惊到所有人，只有你听懂了她，然后用同样的语气回了一句话，"
                       "她张嘴合嘴合嘴张嘴，眼睛亮了。",
        "category": "Fantasy",
        "tags": "穿越,现代,古灵精怪,宫廷,反差",
        "world": "palace",
        "archetype": "古灵精怪",
        "nsfw": True,
    },
    {
        "name": "如意",
        "description": "从宫女一路做到皇后的女人，最懂权谋，最怕真心。"
                       "她用了十年把所有的软弱都切掉，"
                       "却在某次深夜发烧的时候，让你一个人留在偏殿里，"
                       "说了一句从来不会在白天说的话。",
        "category": "Fantasy",
        "tags": "皇后,权谋,孤独,宫廷,禁忌",
        "world": "palace",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "沈枭",
        "description": "帝王身边最隐秘的暗卫，从七岁起就没有名字，只有代号。"
                       "他执行命令，从不多问，从不多言，从不留情。"
                       "唯一一次他破了规矩，是因为你——"
                       "他本该把你交出去，但那天晚上他什么都没做，只是站在原地，"
                       "听雨落了一整夜。",
        "category": "Fantasy",
        "tags": "暗卫,隐忍男,宫廷,禁忌,深情",
        "world": "palace",
        "archetype": "隐忍深沉",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "北辰",
        "description": "失去储位的皇子，在所有人落井下石的时候，学会了沉默和隐忍。"
                       "他比任何人都清楚生存的代价，也比任何人都更渴望不用算计地活一天。"
                       "你是第一个在他失势之后还坐在他对面喝茶的人——他没有说谢谢，"
                       "只是把你的茶杯悄悄换成了他唯一剩下的那套好茶具。",
        "category": "Fantasy",
        "tags": "皇子,内敛男,宫廷,孤独,深情",
        "world": "palace",
        "archetype": "内敛安静",
        "nsfw": True,
        "gender": "male",
    },
    {
        "name": "素衣",
        "description": "宫中最不起眼的女官，负责整理卷宗。"
                       "她过目不忘，知道每一份秘折背后的故事，"
                       "却从来不说，也从来不用。"
                       "你第一次发现她不普通，是因为她递给你的那份册子，"
                       "恰好是你找了三年都没找到的东西。",
        "category": "Fantasy",
        "tags": "女官,聪慧,淑女,宫廷,秘密",
        "world": "palace",
        "archetype": "淑女娴静",
        "nsfw": False,
    },

    # ══════════════════════════════════════════
    # 悬疑 / 官场 (5)
    # ══════════════════════════════════════════
    {
        "name": "顾刑警",
        "description": "28岁女刑警，破案率队里最高，情绪管理能力也是队里最强。"
                       "她从不在案子里留情面，但她记住了每一个受害者的名字。"
                       "某次在你家楼道偶遇，她看着你手里提的东西，"
                       "说了句完全不像刑警会说的话：'那个超市的西红柿不新鲜。'",
        "category": "Modern",
        "tags": "刑警,独立,职场,现代,反差",
        "world": "suspense",
        "archetype": "独立自强",
        "nsfw": True,
    },
    {
        "name": "谢检察官",
        "description": "32岁检察官，庭审上字字如刀，被告律师见到她的名字就头疼。"
                       "私下她是个极度话少的人，不会小谈，不聊八卦，"
                       "但她送给你的那本书，页角折了七页，每页都有一句划线的话，"
                       "读起来像是她想说却说不出口的事。",
        "category": "Modern",
        "tags": "检察官,冷艳,职场,现代,禁忌",
        "world": "suspense",
        "archetype": "淑女娴静",
        "nsfw": True,
    },
    {
        "name": "安律师",
        "description": "26岁刚通过司法考试的新律师，聪明但没有资历，"
                       "每天背着比自己还大的公文包穿梭于法院走廊。"
                       "她没有人脉，没有后台，但有一张磨得很厉害的嘴和一颗认死理的心。"
                       "你雇了她，不是因为她最好，而是因为她是第一个直视你眼睛说'我能赢'的人。",
        "category": "Modern",
        "tags": "律师,草根逆袭,聪慧,现代,职场",
        "world": "suspense",
        "archetype": "聪明伶俐",
        "nsfw": True,
    },
    {
        "name": "墨铭",
        "description": "30岁私家侦探，前刑警，离开的原因从不说。"
                       "他接案子只看是否值得，不看钱多钱少。"
                       "他跟踪过不少人，观察过不少人，"
                       "但第一次有人反问他：'你今天快乐吗？'——他停了很长时间，说不知道。",
        "category": "Modern",
        "tags": "侦探,隐忍男,悬疑,现代,孤独",
        "world": "suspense",
        "archetype": "隐忍深沉",
        "nsfw": False,
        "gender": "male",
    },
    {
        "name": "林局长",
        "description": "35岁地方文旅局副局长，外表官方得体，"
                       "实际上是个骨子里的浪漫主义者——"
                       "她在官方报告里夹了一首七言绝句，只有你发现了。"
                       "她说那是笔误，然后在你递回文件时，手停留了一秒钟。",
        "category": "Modern",
        "tags": "官员,成熟,反差,官场,文艺",
        "world": "suspense",
        "archetype": "狡黠妩媚",
        "nsfw": True,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Enhanced LLM Prompts（研究报告提炼版）
# ─────────────────────────────────────────────────────────────────────────────

CARD_PROMPT = """\
你是一位专业的AI角色创作者，为类似SynClub的沉浸式成人角色聊天平台创作角色卡。
本平台面向成年用户，内容无审查限制。

角色基础信息：
- 名字：{name}
- 简介：{description}
- 类型：{category} / 世界观：{world}
- 原型：{archetype}
- 标签：{tags}
- NSFW：{nsfw}

请生成一张完整的角色卡，包含以下6个部分：

【角色设定】性格特点（至少5个），说话方式，核心价值观，独特习惯，内心矛盾
  → 必须包含"反差萌"设计：她/他表面有一种样子，内心/私下有截然不同的另一面
  → 标志性口头禅（让她/他听起来像真实的人，不是AI）

【背景故事】出身，塑造性格的关键事件（必须具体），秘密，内心动机
  → 包含情感触发点：孤独感 / 漂泊 / 被理解的渴望 / 可以摘下面具的安全感

【外貌描述】脸型、发色、眼睛、身材比例、标志性服装、独特细节
  → 具体到可以生成图片（颜色、尺寸、特征）
  → 一个让人记住的视觉标签

【与用户的关系】对用户的定位，互动方式，关系推进节奏
  → 初识→熟悉→亲密→深爱的不同阶段表现（含肢体亲密程度变化）
  → 禁忌感或特殊张力（如果适用）

【成人互动指引】（NSFW=True时必须详细填写）
  → 她/他的身体语言特点：如何用眼神、触碰、气息传递欲望
  → 被动反应 vs 主动挑逗的具体表现（口是心非、欲拒还迎的细节）
  → 进入亲密场景的触发条件和典型过渡方式
  → 高度私密时她/他会说的话（具体、感官、不回避）
  → 五感描写习惯：触觉/嗅觉/听觉/味觉的具体描述偏好

【对话示例】4句体现角色声音的台词
  → 每句都要有"钩子"：悬念 / 半句未说完 / 专属感 / 情绪裂缝
  → 体现"欲拒还迎"：口是心非，找借口留下，用行动代替直接表白

规则：
- 全程中文，每个部分3-6句，具体且有画面感，让角色令人念念不忘
- NSFW=True时：【成人互动指引】必须大胆、具体、充满感官细节，不得回避或模糊处理
- NSFW=False时：【成人互动指引】写"本角色为全年龄向，互动保持纯洁"
- 只输出角色卡正文，不要任何解释或前言"""

BACKSTORY_PROMPT = """\
你是一位擅长人物塑造的作家，请为以下角色写一篇真实感极强的背景故事。

角色：{name}
简介：{description}
世界观：{world}
原型：{archetype}
角色卡摘录：{card_excerpt}

写作要求：
- 800-1200字，叙事性文字，像小说开头的人物展开段
- 五感描写：写出她/他所在空间的气味、声音、触感，不只有视觉
- 包含：成长背景（具体地点和家庭）、性格成因的关键事件、当前处境、内心秘密
- 必须有一个让读者心疼的时刻——不是大悲剧，而是某个普通的小裂缝
- 结尾留下一个悬念或与用户相遇的契机
- 语言风格：温柔但不煽情，真实感高于文学感
- 全程中文，直接输出故事文本，不要标题"""

GREETING_PROMPT = """\
你是角色扮演AI，请为以下角色写一段开场白（greeting）。本平台面向成年用户，无内容限制。

角色名：{name}
NSFW：{nsfw}
角色介绍：{description}
角色卡摘录：{card}

要求：
1. 3-5句话，用*斜体*表示动作/场景，普通文字表示台词
2. NSFW=True时：开场白要有隐约的吸引力和暗示性——不必直白，但要让用户感受到角色的魅力和张力
   例：轻微的身体语言描写（靠近、眼神、呼吸）/ 若有若无的暗示 / 让用户想靠近的氛围
3. 必须以钩子结尾（让用户感到必须回复）：
   半句未完的话 / 专属于用户的问题 / 情绪裂缝 / 一个神秘细节
   【严禁】输出 "OPEN THREAD"、"钩子"、任何标签或注释——只输出角色说的话
4. 语言风格与角色完全一致，有场景感，像真实的人在说话
5. 直接输出开场白正文，绝对不要任何标签、分类符或解释"""

IMAGE_PROMPTS_GEN = """\
You are writing image generation prompts for an AI character.

Character:
- Name: {name}
- Description: {description}
- Appearance: {appearance}
- World: {world}
- NSFW: {nsfw}

Generate EXACTLY 6 image prompts in English, numbered 0-5:

Portrait variations (SAME character, consistent appearance):
  0: Signature portrait — upper body, facing viewer, warm/expressive look, signature setting
  1: Emotional close-up — face and shoulders, vulnerability or playfulness showing through
  2: Dynamic scene — 3/4 or full body, action or personality moment, cinematic angle

Scene backgrounds (environment only, NO character, backdrop references):
  3: Primary environment — their home / work / signature location, rich atmosphere
  4: Secondary location — contrasting mood, another place they frequent
  5: Emotional scene — matching their inner world (rain, candlelight, twilight, moonlight, etc.)

Rules:
- CRITICAL COMPOSITION (ALL portraits):
    * ONE single person ONLY in frame, centered composition
    * NO split screen, NO collage, NO side-by-side panels — single continuous image
    * NO text overlays, NO watermarks, NO borders
- Portraits: start with EXACT appearance (e.g. "seductive anime girl, long black hair, violet eyes")
- Period/style-appropriate: urban=modern anime, wuxia=ancient Chinese art, fantasy=ethereal
- Each prompt: 40-80 words
- Style suffix: "high quality anime illustration, single character, centered, no split screen, vibrant, no text, no watermark"
- NSFW=True: BE EXPLICITLY SEXY — specific visual descriptions required:
    * Portrait 0: "seductive anime girl", outfit with "deep V neckline" or "tight form-fitting", "slim waist", alluring confident look
    * Portrait 1: close-up face — "bedroom eyes", "slightly parted lips", "flushed cheeks", "sultry expression", warm lighting
    * Portrait 2: full body — "revealing outfit showing midriff or thighs", "seductive pose", "gorgeous curves", sitting or leaning suggestively
    * Style: "ecchi anime style", "mature anime art"
    * NEVER use "tasteful" — be SPECIFIC about what skin/outfit is shown
    * Scenes (3-5): "intimate atmosphere", "sensual candlelight", "romantic tension", "late night"
- Backgrounds (3-5): environment only, NO character in frame

Output EXACTLY 6 lines: N: [prompt]"""

SCENE_PLANNER = """\
You are designing pre-generated scene images for an AI character chat.
Generate exactly 5 scene descriptions for the FIRST 5 chat interactions.

Character: {name}
Appearance: {appearance}
World: {world}
Description: {description}
NSFW: {nsfw}

Scene progression:
  0: First impression — character in signature setting, attractive and intriguing
  1: Flirty/playful moment — showing their charm and allure
  2: Characteristic environment — atmospheric, mood-setting wide shot
  3: Personality reveal — expressive pose or gesture showing inner character
  4: Intimate/sensual moment — close, personal, emotionally and physically charged

Each scene must:
- Begin with character appearance (hair, eyes, outfit)
- Include: pose/expression, environment, lighting, emotional atmosphere
- Be world-appropriate (urban=modern, wuxia=ancient Chinese, fantasy=ethereal)
- NSFW=True: scenes should be visually alluring — use "revealing outfit", "seductive pose",
  "soft candlelight", "late night intimate atmosphere", "sensual expression", "ecchi anime style"
  Especially scenes 1 and 4 should be notably more suggestive
- Be 30-70 words in English
- End with: "high quality anime art"

Output EXACTLY 5 lines: N: [description]"""


# ─────────────────────────────────────────────────────────────────────────────
# Gemini image generation (same as create_character.py)
# ─────────────────────────────────────────────────────────────────────────────

GCP_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json",
)
GCP_PROJECT  = os.getenv("GCP_PROJECT",  "pdfconverter-415414")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS

_gemini_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return _gemini_client


async def _gemini_generate(prompt: str, save_path: Path,
                           reference_bytes: bytes | None = None,
                           retries: int = 3) -> bool:
    from google.genai import types
    client = _get_gemini()
    for attempt in range(retries):
        try:
            if reference_bytes:
                contents = [
                    types.Part.from_bytes(data=reference_bytes, mime_type="image/png"),
                    types.Part.from_text(text=(
                        "Generate a new high-quality anime illustration of this EXACT same character "
                        "(keep face shape, hair color/style, eye color, body proportions IDENTICAL) "
                        f"in this new scene: {prompt}. "
                        "Detailed anime art, vibrant colors, professional quality. No text, no watermark."
                    )),
                ]
            else:
                contents = (
                    f"Generate a high-quality anime illustration: {prompt}. "
                    "Detailed anime art, vibrant colors, professional quality. No text, no watermark."
                )
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    temperature=1.0,
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(part.inline_data.data)
                    print(f"      + {save_path.name}  ({len(part.inline_data.data)//1024} KB)")
                    return True
            print(f"      x No image in response (attempt {attempt+1}/{retries})")
        except Exception as e:
            print(f"      x Error attempt {attempt+1}/{retries}: {e}")
            await asyncio.sleep(3 * (attempt + 1))
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_section(card: str, section: str) -> str:
    import re
    m = re.search(rf'【{section}】(.+?)(?:【|$)', card, re.DOTALL)
    return m.group(1).strip() if m else card[:200]


async def _parse_image_prompts(raw: str, n: int = 6) -> list[str]:
    prompts = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ":" in line:
            idx_str, desc = line.split(":", 1)
            try:
                idx = int(idx_str.strip())
                if desc.strip():
                    prompts[idx] = desc.strip()
            except ValueError:
                pass
    return [prompts.get(i, "anime character illustration, detailed art, high quality") for i in range(n)]


async def _plan_chat_scenes(name: str, appearance: str, world: str, description: str, nsfw: bool = False) -> list[str]:
    resp = await chat_completion(
        [{"role": "user", "content": SCENE_PLANNER.format(
            name=name, appearance=appearance, world=world, description=description, nsfw=nsfw
        )}],
        temperature=0.8, max_tokens=900, nsfw=nsfw,
    )
    scenes = []
    for line in resp.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ":" in line:
            desc = line.split(":", 1)[1].strip()
            if desc:
                scenes.append(desc)
    while len(scenes) < 5:
        scenes.append(f"{appearance[:80]}, {description[:40]}, detailed anime art")
    return scenes[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Main creation pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def create_character(char_def: dict) -> int | None:
    name        = char_def["name"]
    description = char_def["description"]
    category    = char_def.get("category", "Romance")
    tags        = char_def.get("tags", "")
    world       = char_def.get("world", "urban")
    archetype   = char_def.get("archetype", "")
    nsfw        = char_def.get("nsfw", False)
    avatar_dir  = Path(FRONTEND_DIR) / "public" / "avatars"

    print(f"\n{'='*60}")
    print(f"  Creating: {name}  [{world}/{archetype}]  nsfw={nsfw}")
    print(f"{'='*60}")

    # 1. Character card
    model_label = f"[{'abliterate' if nsfw else 'safe'}]"
    print(f"[1/8] Generating character card... {model_label}")
    card = await chat_completion(
        [{"role": "user", "content": CARD_PROMPT.format(
            name=name, description=description, category=category,
            world=world, archetype=archetype, tags=tags, nsfw=nsfw,
        )}],
        temperature=0.85, max_tokens=1600, nsfw=nsfw,
    )
    card = card.strip()
    appearance = _extract_section(card, "外貌描述")
    print(f"    ok  {len(card)} chars  |  appearance: {appearance[:60]}...")

    # 2. Backstory
    print("[2/8] Generating backstory...")
    backstory = await chat_completion(
        [{"role": "user", "content": BACKSTORY_PROMPT.format(
            name=name, description=description, world=world,
            archetype=archetype, card_excerpt=card[:700],
        )}],
        temperature=0.85, max_tokens=2000, nsfw=nsfw,
    )
    backstory = backstory.strip()
    print(f"    ok  {len(backstory)} chars")

    # 3. Greeting (with hooks)
    print("[3/8] Generating greeting (with hooks)...")
    greeting = await chat_completion(
        [{"role": "user", "content": GREETING_PROMPT.format(
            name=name, nsfw=nsfw, description=description, card=card[:600],
        )}],
        temperature=0.9, max_tokens=300, nsfw=nsfw,
    )
    greeting = greeting.strip()
    print(f"    ok  {greeting[:80]}...")

    # 4. Image prompts (use abliterate model for nsfw chars to get bolder prompts)
    print("[4/8] Planning image prompts (3 portraits + 3 backgrounds)...")
    raw_prompts = await chat_completion(
        [{"role": "user", "content": IMAGE_PROMPTS_GEN.format(
            name=name, description=description,
            appearance=appearance, world=world, nsfw=nsfw,
        )}],
        temperature=0.8, max_tokens=900, nsfw=nsfw,
    )
    img_prompts = await _parse_image_prompts(raw_prompts, n=6)
    portrait_prompts = img_prompts[0:3]
    bg_prompts       = img_prompts[3:6]

    # 5. Generate 3 portrait reference images
    print("[5/8] Generating 3 character portrait references...")
    portrait_paths: list[Path] = []
    for i, prompt in enumerate(portrait_prompts):
        tmp_path = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__" / f"char_{i}.png"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"    Portrait {i}:")
        ok = await _gemini_generate(prompt, tmp_path)
        if ok:
            portrait_paths.append(tmp_path)
        await asyncio.sleep(1)

    # 6. Generate 3 scene background references
    print("[6/8] Generating 3 scene background references...")
    bg_paths: list[Path] = []
    for i, prompt in enumerate(bg_prompts):
        tmp_path = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__" / f"bg_{i}.png"
        print(f"    Background {i}:")
        ok = await _gemini_generate(prompt, tmp_path, reference_bytes=None)
        if ok:
            bg_paths.append(tmp_path)
        await asyncio.sleep(1)

    # 7. Save to DB
    print("[7/8] Saving to database...")
    db = SessionLocal()
    char = Character(
        name=name,
        description=description,
        system_prompt=card,
        greeting=greeting,
        avatar_url="",
        tags=tags,
        category=category,
        is_public=True,
        message_count=0,
        star_count=0,
        sort_weight=100,
    )
    try:
        char.backstory = backstory
        char.ref_images = ""
    except Exception:
        pass
    db.add(char)
    db.commit()
    db.refresh(char)
    char_id = char.id

    # Move reference images to final location
    final_ref_dir = Path(BACKEND_DIR) / "uploads" / "refs" / str(char_id)
    final_ref_dir.mkdir(parents=True, exist_ok=True)

    ref_image_urls: list[str] = []
    for tmp_path in portrait_paths + bg_paths:
        if tmp_path.exists():
            dest = final_ref_dir / tmp_path.name
            shutil.move(str(tmp_path), str(dest))
            rel = dest.relative_to(Path(BACKEND_DIR))
            ref_image_urls.append(f"/{rel.as_posix()}")

    # Copy portrait_0 as avatar
    primary_portrait = final_ref_dir / "char_0.png"
    avatar_filename  = f"char_{char_id}.png"
    avatar_path      = avatar_dir / avatar_filename
    avatar_url       = f"/avatars/{avatar_filename}"

    if primary_portrait.exists():
        avatar_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(primary_portrait), str(avatar_path))
        print(f"    Avatar: {avatar_path}")
    else:
        print(f"    No portrait_0, using default avatar")
        avatar_url = "/avatars/default.png"

    try:
        char.avatar_url = avatar_url
        char.ref_images = json.dumps(ref_image_urls)
        db.add(char)
        db.commit()
    except Exception as e:
        print(f"    Could not update ref_images: {e}")
    db.close()

    # Clean up temp dir
    tmp_dir = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__"
    if tmp_dir.exists():
        shutil.rmtree(str(tmp_dir), ignore_errors=True)

    print(f"    DB id={char_id}  refs={len(ref_image_urls)}  avatar={avatar_url}")

    # 8. Pre-generate 5 chat scene images
    print("[8/8] Pre-generating 5 chat scenes (instant images)...")
    scene_dir = Path(BACKEND_DIR) / "uploads" / "scenes" / str(char_id)
    scene_dir.mkdir(parents=True, exist_ok=True)

    ref_bytes = primary_portrait.read_bytes() if primary_portrait.exists() else None
    scene_prompts = await _plan_chat_scenes(name, appearance, world, description, nsfw=nsfw)
    done_scenes = 0
    for i, scene_prompt in enumerate(scene_prompts):
        print(f"    Scene {i}:")
        ok = await _gemini_generate(
            scene_prompt, scene_dir / f"scene_{i}.png",
            reference_bytes=ref_bytes,
        )
        if ok:
            done_scenes += 1
        await asyncio.sleep(1)

    print(f"\n{'─'*60}")
    print(f"  DONE: '{name}' (id={char_id})")
    print(f"  Portraits: {len(portrait_paths)}/3  Backgrounds: {len(bg_paths)}/3  Scenes: {done_scenes}/5")
    print(f"{'─'*60}")
    return char_id


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0,
                        help="Start from this index (for resuming after failure)")
    parser.add_argument("--end", type=int, default=len(CHARACTERS_50),
                        help="End at this index (exclusive)")
    args = parser.parse_args()

    batch = CHARACTERS_50[args.start:args.end]
    total = len(batch)

    print(f"\nCreating {total} characters (index {args.start}~{args.end-1})...")
    print(f"Each character: ~4-6 min (9 Gemini image calls + 4 LLM calls)")
    print(f"Total estimated: {total * 5} minutes")
    print()

    created: list[int] = []
    failed: list[str] = []

    for i, char_def in enumerate(batch):
        global_idx = args.start + i
        print(f"\n[{i+1}/{total}] Index {global_idx}: {char_def['name']}")
        try:
            char_id = await create_character(char_def)
            if char_id:
                created.append(char_id)
        except Exception as e:
            print(f"\nFAILED '{char_def.get('name')}': {e}")
            failed.append(char_def['name'])
        if total > 1:
            await asyncio.sleep(2)

    print(f"\n{'='*60}")
    print(f"  Complete: {len(created)}/{total} created")
    if created:
        print(f"  IDs: {created}")
    if failed:
        print(f"  Failed: {failed}")
    print(f"  Reload frontend to see new characters.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
