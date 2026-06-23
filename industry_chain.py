"""
蓝宝书Max · 产业链映射引擎
将Alpha派主题→产业链上下游→精准短线标的
"""
import re
from typing import List, Dict, Optional

class ChainNode:
    """产业链节点"""
    def __init__(self, name: str, stocks: List[Dict], role: str = ""):
        self.name = name          # 节点名称（上游/中游/下游）
        self.role = role          # 角色描述
        self.stocks = stocks      # [{"name":"", "code":"", "catalyst":"", "alpha":0}]

class IndustryChain:
    """产业链"""
    def __init__(self, name: str, nodes: List[ChainNode], key_driver: str = ""):
        self.name = name
        self.nodes = nodes
        self.key_driver = key_driver  # 核心驱动逻辑

# ===== 产业链映射库 =====
# 关键词 → 产业链

CHAIN_DB: Dict[str, IndustryChain] = {
    # ===== AI/半导体 =====
    "氧化锆": IndustryChain("氧化锆产业链", [
        ChainNode("上游·原料", [
            {"name": "东方锆业", "code": "002167", "catalyst": "锆矿资源+氯氧化锆", "alpha": 76},
            {"name": "龙佰集团", "code": "002601", "catalyst": "氯氧化锆产能最大", "alpha": 60},
            {"name": "三祥新材", "code": "603663", "catalyst": "电熔氧化锆龙头", "alpha": 57},
        ], "锆矿→氯氧化锆→氧化锆粉体"),
        ChainNode("中游·粉体", [
            {"name": "国瓷材料", "code": "300285", "catalyst": "粉体龙头+国产替代", "alpha": 75},
            {"name": "东方锆业", "code": "002167", "catalyst": "粉体一体化", "alpha": 76},
        ], "氧化锆粉体→成型→烧结"),
        ChainNode("下游·制品", [
            {"name": "爱迪特", "code": "301580", "catalyst": "齿科材料+海外订单", "alpha": 77},
            {"name": "国瓷材料", "code": "300285", "catalyst": "齿科+电子陶瓷", "alpha": 75},
        ], "齿科材料+电子陶瓷+结构件"),
    ], "日本东曹断供→国产替代窗口打开"),

    "MLCC|陶瓷电容|片容": IndustryChain("MLCC产业链", [
        ChainNode("上游·粉体", [
            {"name": "国瓷材料", "code": "300285", "catalyst": "钛酸钡粉体龙头", "alpha": 75},
            {"name": "博迁新材", "code": "605376", "catalyst": "镍粉国产替代", "alpha": 49},
        ], "陶瓷粉体+电极材料"),
        ChainNode("中游·器件", [
            {"name": "三环集团", "code": "300408", "catalyst": "MLCC龙头+涨价受益", "alpha": 57},
            {"name": "风华高科", "code": "000636", "catalyst": "国产MLCC龙头", "alpha": 52},
            {"name": "火炬电子", "code": "603678", "catalyst": "特种MLCC", "alpha": 44},
        ], "MLCC/电感制造"),
        ChainNode("下游·渠道", [
            {"name": "商络电子", "code": "300975", "catalyst": "分销商+库存升值", "alpha": 37},
            {"name": "深圳华强", "code": "000062", "catalyst": "最大电子分销", "alpha": 31},
        ], "电子元器件分销"),
    ], "日系涨价→国产替代加速"),

    "CCL|覆铜板|PCB": IndustryChain("CCL/PCB产业链", [
        ChainNode("上游·材料", [
            {"name": "中国巨石", "code": "600176", "catalyst": "电子布龙头", "alpha": 49},
            {"name": "宏和科技", "code": "603256", "catalyst": "电子布弹性最大", "alpha": 42},
            {"name": "铜冠铜箔", "code": "301217", "catalyst": "电子铜箔", "alpha": 35},
            {"name": "圣泉集团", "code": "605589", "catalyst": "树脂供应商", "alpha": 38},
        ], "电子布+铜箔+树脂"),
        ChainNode("中游·CCL", [
            {"name": "生益科技", "code": "600183", "catalyst": "CCL龙头+涨价", "alpha": 61},
            {"name": "金安国纪", "code": "002636", "catalyst": "CCL直接受益", "alpha": 67},
            {"name": "华正新材", "code": "603186", "catalyst": "利润率弹性", "alpha": 48},
        ], "覆铜板制造"),
        ChainNode("下游·PCB", [
            {"name": "深南电路", "code": "002916", "catalyst": "高端PCB龙头", "alpha": 40},
            {"name": "兴森科技", "code": "002436", "catalyst": "mSAP板核心", "alpha": 45},
            {"name": "鹏鼎控股", "code": "002938", "catalyst": "FPC龙头", "alpha": 39},
        ], "PCB制造+封装基板"),
    ], "建滔涨价→全产业链传导"),

    "AI算力|AI芯片|昇腾|寒武纪": IndustryChain("AI算力芯片产业链", [
        ChainNode("上游·设计/IP", [
            {"name": "芯原股份", "code": "688521", "catalyst": "ASIC设计服务", "alpha": 45},
        ], "芯片设计+IP授权"),
        ChainNode("中游·芯片", [
            {"name": "寒武纪", "code": "688256", "catalyst": "AI芯片龙头+涨价", "alpha": 61},
            {"name": "海光信息", "code": "688041", "catalyst": "DCU国产替代", "alpha": 56},
        ], "AI训练/推理芯片"),
        ChainNode("下游·制造/应用", [
            {"name": "中芯国际", "code": "688981", "catalyst": "晶圆代工", "alpha": 38},
            {"name": "华虹公司", "code": "688347", "catalyst": "特色工艺代工", "alpha": 39},
        ], "晶圆制造+封装测试"),
    ], "国产芯片涨价+订单爆发"),

    "光模块|光通信|CPO": IndustryChain("AI光模块产业链", [
        ChainNode("上游·光芯片", [
            {"name": "仕佳光子", "code": "688313", "catalyst": "光芯片+CPO组件", "alpha": 42},
            {"name": "云南锗业", "code": "002428", "catalyst": "磷化铟衬底", "alpha": 66},
        ], "光芯片+化合物半导体"),
        ChainNode("中游·器件", [
            {"name": "太辰光", "code": "300570", "catalyst": "光器件龙头", "alpha": 42},
            {"name": "光智科技", "code": "300489", "catalyst": "磷化铟衬底", "alpha": 60},
        ], "光器件+光模块组件"),
        ChainNode("下游·模块", [
            {"name": "中际旭创", "code": "300308", "catalyst": "800G光模块龙头", "alpha": 20},
            {"name": "新易盛", "code": "300502", "catalyst": "400G/800G放量", "alpha": 20},
        ], "光模块组装+测试"),
    ], "800G升级→全链受益"),

    "光纤|光缆|藤仓": IndustryChain("光纤光缆产业链", [
        ChainNode("上游·预制棒", [
            {"name": "长飞光纤", "code": "601869", "catalyst": "光纤预制棒龙头", "alpha": 73},
            {"name": "中天科技", "code": "600522", "catalyst": "棒纤缆一体化", "alpha": 55},
        ], "光纤预制棒+涂料"),
        ChainNode("中游·光纤缆", [
            {"name": "烽火通信", "code": "600498", "catalyst": "光纤缆龙头", "alpha": 65},
            {"name": "亨通光电", "code": "600487", "catalyst": "海缆+光纤", "alpha": 68},
        ], "光纤拉丝+成缆"),
        ChainNode("下游·连接器", [
            {"name": "瑞松科技", "code": "688090", "catalyst": "MPO自动化", "alpha": 33},
            {"name": "太辰光", "code": "300570", "catalyst": "MPO连接器", "alpha": 42},
        ], "光连接器+配线架"),
    ], "藤仓涨价+AI拉动需求"),

    "液冷|散热|Rubin": IndustryChain("AI液冷散热产业链", [
        ChainNode("上游·冷板/管路", [
            {"name": "强瑞技术", "code": "301128", "catalyst": "Rubin液冷歧管", "alpha": 51},
            {"name": "飞龙股份", "code": "002536", "catalyst": "电子水泵", "alpha": 40},
        ], "冷板+管路+水泵"),
        ChainNode("中游·CDU", [
            {"name": "裕同科技", "code": "002831", "catalyst": "MIM液冷结构件", "alpha": 24},
        ], "CDU+Manifold"),
        ChainNode("下游·数据中心", [
            {"name": "科华数据", "code": "002335", "catalyst": "数据中心电源", "alpha": 24},
            {"name": "金盘科技", "code": "688676", "catalyst": "变压器+SST", "alpha": 36},
        ], "数据中心供电+散热"),
    ], "英伟达Rubin全面液冷"),

    "存储|DRAM|NAND|HBM": IndustryChain("存储芯片产业链", [
        ChainNode("上游·晶圆", [
            {"name": "中芯国际", "code": "688981", "catalyst": "存储代工", "alpha": 38},
        ], "晶圆制造"),
        ChainNode("中游·芯片设计", [
            {"name": "兆易创新", "code": "603986", "catalyst": "NOR Flash龙头", "alpha": 47},
            {"name": "普冉股份", "code": "688766", "catalyst": "利基存储", "alpha": 49},
        ], "存储芯片设计"),
        ChainNode("下游·模组/分销", [
            {"name": "江波龙", "code": "301308", "catalyst": "模组龙头+涨价弹性", "alpha": 57},
            {"name": "佰维存储", "code": "688525", "catalyst": "企业级存储", "alpha": 57},
            {"name": "香农芯创", "code": "300475", "catalyst": "HBM代理", "alpha": 50},
        ], "存储模组+分销"),
    ], "DDR5涨288%→全链景气"),

    # ===== 新能源 =====
    "逆变器|储能|户储": IndustryChain("逆变器/储能产业链", [
        ChainNode("上游·IGBT", [
            {"name": "斯达半导", "code": "603290", "catalyst": "IGBT国产替代"},
            {"name": "时代电气", "code": "688187", "catalyst": "功率半导体"},
        ], "功率器件+磁性元件"),
        ChainNode("中游·逆变器", [
            {"name": "德业股份", "code": "605117", "catalyst": "欧洲户储龙头", "alpha": 54},
            {"name": "固德威", "code": "688390", "catalyst": "组串式逆变器", "alpha": 50},
            {"name": "锦浪科技", "code": "300763", "catalyst": "组串式龙头", "alpha": 51},
        ], "逆变器制造"),
        ChainNode("下游·集成/EPC", [
            {"name": "阳光电源", "code": "300274", "catalyst": "储能系统集成", "alpha": 41},
            {"name": "科华数据", "code": "002335", "catalyst": "数据中心+储能", "alpha": 24},
        ], "系统集成+EPC"),
    ], "欧盟对华贸易缓和"),

    "海风|风电|塔筒": IndustryChain("海上风电产业链", [
        ChainNode("上游·材料", [
            {"name": "光威复材", "code": "300699", "catalyst": "碳纤维叶片"},
            {"name": "新强联", "code": "300850", "catalyst": "主轴轴承", "alpha": 39},
        ], "碳纤维+钢材+轴承"),
        ChainNode("中游·部件", [
            {"name": "大金重工", "code": "002487", "catalyst": "塔筒+导管架", "alpha": 47},
            {"name": "天顺风能", "code": "002531", "catalyst": "塔筒+叶片", "alpha": 37},
        ], "塔筒+叶片+铸件"),
        ChainNode("下游·安装/运营", [
            {"name": "明阳智能", "code": "601615", "catalyst": "海上风机龙头"},
        ], "风机安装+风场运营"),
    ], "欧洲海风需求爆发"),

    # ===== 战略资源 =====
    "铟|磷化铟": IndustryChain("铟/磷化铟产业链", [
        ChainNode("上游·矿冶", [
            {"name": "锡业股份", "code": "000960", "catalyst": "铟产量全球第一", "alpha": 54},
            {"name": "株冶集团", "code": "600961", "catalyst": "铟冶炼龙头", "alpha": 54},
            {"name": "驰宏锌锗", "code": "600497", "catalyst": "铟锌伴生矿", "alpha": 54},
        ], "铟矿开采+冶炼"),
        ChainNode("中游·衬底", [
            {"name": "云南锗业", "code": "002428", "catalyst": "磷化铟衬底龙头", "alpha": 66},
            {"name": "光智科技", "code": "300489", "catalyst": "磷化铟衬底", "alpha": 60},
        ], "磷化铟衬底生长"),
        ChainNode("下游·器件", [
            {"name": "仕佳光子", "code": "688313", "catalyst": "光通信芯片", "alpha": 42},
        ], "光通信+射频器件"),
    ], "海关加强铟出口审查"),

    # ===== 机器人 =====
    "机器人|特斯拉|Optimus": IndustryChain("人形机器人产业链", [
        ChainNode("上游·零部件", [
            {"name": "斯菱智驱", "code": "301550", "catalyst": "谐波减速器", "alpha": 41},
            {"name": "科达利", "code": "002850", "catalyst": "谐波减速器", "alpha": 43},
            {"name": "峰岹科技", "code": "688279", "catalyst": "电机驱动芯片", "alpha": 38},
        ], "减速器+电机+传感器"),
        ChainNode("中游·执行器", [
            {"name": "三花智控", "code": "002050", "catalyst": "执行器总成", "alpha": 49},
            {"name": "拓普集团", "code": "601689", "catalyst": "电驱总成", "alpha": 52},
        ], "旋转/线性执行器"),
        ChainNode("下游·结构件", [
            {"name": "恒立液压", "code": "601100", "catalyst": "丝杠环节", "alpha": 30},
            {"name": "贝斯特", "code": "300580", "catalyst": "丝杠+壳体", "alpha": 34},
            {"name": "福赛科技", "code": "301529", "catalyst": "PEEK轻量化", "alpha": 33},
        ], "丝杠+轻量化材料"),
    ], "特斯拉得州工厂进度超预期"),

    "陶瓷基板|氮化铝|AlN": IndustryChain("陶瓷基板产业链", [
        ChainNode("上游·粉体", [
            {"name": "国瓷材料", "code": "300285", "catalyst": "多品类陶瓷粉体", "alpha": 75},
            {"name": "金博股份", "code": "688598", "catalyst": "氮化铝粉体新产能", "alpha": 51},
        ], "高纯氮化铝/氧化铝粉体"),
        ChainNode("中游·基板", [
            {"name": "旭光电子", "code": "600353", "catalyst": "全产业链布局", "alpha": 68},
            {"name": "中瓷电子", "code": "003031", "catalyst": "氮化铝外壳批量供货", "alpha": 68},
        ], "陶瓷基板成型+金属化"),
        ChainNode("下游·封装", [
            {"name": "楚江新材", "code": "002171", "catalyst": "烧结设备", "alpha": 31},
        ], "芯片封装+光模块外壳"),
    ], "日本供给受限+AI需求爆发"),

    "玻璃基板|TGV|蓝思": IndustryChain("玻璃基板产业链", [
        ChainNode("上游·玻璃原片", [
            {"name": "彩虹股份", "code": "600707", "catalyst": "基板玻璃龙头", "alpha": 57},
            {"name": "凯盛科技", "code": "600552", "catalyst": "显示+基板玻璃", "alpha": 53},
        ], "高硼硅玻璃原片"),
        ChainNode("中游·TGV加工", [
            {"name": "蓝思科技", "code": "300433", "catalyst": "TGV技术突破+官媒确认", "alpha": 54},
        ], "TGV通孔+金属化"),
        ChainNode("下游·封装", [
            {"name": "深南电路", "code": "002916", "catalyst": "先进封装基板", "alpha": 40},
        ], "先进封装+玻璃基转接板"),
    ], "央视报道蓝思TGV突破"),

    # ===== 其他 =====
    "燃气轮机|数据中心电力|FERC": IndustryChain("数据中心电力产业链", [
        ChainNode("上游·核心部件", [
            {"name": "应流股份", "code": "603308", "catalyst": "高温合金叶片", "alpha": 58},
            {"name": "万泽股份", "code": "000534", "catalyst": "高温合金", "alpha": 42},
        ], "高温合金+精密铸件"),
        ChainNode("中游·机组", [
            {"name": "杰瑞股份", "code": "002353", "catalyst": "燃气轮机成套", "alpha": 62},
            {"name": "东方电气", "code": "600875", "catalyst": "重型燃机龙头", "alpha": 53},
        ], "燃气轮机+内燃机组"),
        ChainNode("下游·配电", [
            {"name": "中国西电", "code": "601179", "catalyst": "变压器+SST", "alpha": 33},
            {"name": "金盘科技", "code": "688676", "catalyst": "干式变压器", "alpha": 36},
            {"name": "思源电气", "code": "002028", "catalyst": "SST+电能质量", "alpha": 36},
        ], "变压器+SST+配电"),
    ], "北美数据中心缺电"),

    "模拟芯片|DrMOS|电源管理": IndustryChain("模拟芯片产业链", [
        ChainNode("上游·晶圆", [
            {"name": "华虹公司", "code": "688347", "catalyst": "模拟芯片代工", "alpha": 39},
        ], "成熟制程晶圆代工"),
        ChainNode("中游·芯片设计", [
            {"name": "圣邦股份", "code": "300661", "catalyst": "平台型模拟龙头", "alpha": 57},
            {"name": "思瑞浦", "code": "688536", "catalyst": "信号链龙头", "alpha": 48},
            {"name": "纳芯微", "code": "688052", "catalyst": "隔离+驱动芯片", "alpha": 51},
        ], "信号链+电源管理"),
        ChainNode("下游·专用芯片", [
            {"name": "杰华特", "code": "688141", "catalyst": "DrMOS国产替代", "alpha": 38},
            {"name": "南芯科技", "code": "688484", "catalyst": "电荷泵快充", "alpha": 35},
        ], "DrMOS+快充+专用PMIC"),
    ], "AI服务器功耗提升→模拟芯片爆发"),
}

# ===== 匹配函数 =====
def match_chain(topic_title: str, topic_summary: str = "") -> Optional[IndustryChain]:
    """根据主题标题匹配产业链"""
    text = topic_title + " " + topic_summary
    best_match = None
    best_len = 0

    for pattern, chain in CHAIN_DB.items():
        # 用 | 分割多关键词，都尝试匹配
        keywords = pattern.split("|")
        for kw in keywords:
            if kw in text:
                if len(kw) > best_len:
                    best_len = len(kw)
                    best_match = chain

    return best_match

def get_all_chains() -> Dict[str, IndustryChain]:
    """获取全部产业链"""
    return CHAIN_DB

if __name__ == "__main__":
    # 测试匹配
    tests = [
        "日本东曹暂停供应高端氧化锆粉体",
        "国产AI算力芯片迎涨价与订单双驱动",
        "建滔积层板再次上调CCL价格",
        "存储芯片价格持续上涨或延续至2028年",
        "英伟达Rubin平台推动液冷技术迭代",
    ]
    for t in tests:
        chain = match_chain(t)
        if chain:
            print(f"✅ {t[:40]}... → {chain.name}")
        else:
            print(f"❌ {t[:40]}... → 无匹配")
