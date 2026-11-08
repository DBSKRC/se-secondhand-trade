from pathlib import Path
import base64, html, json, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'设计源稿'; SRC.mkdir(exist_ok=True)
BG='#F7F5F2'; INK='#292529'; MUT='#777176'; ACC='#792D3C'; PALE='#F2E6E8'; LINE='#E8E2DE'; WHITE='#FFFFFF'
photos=list(ROOT.parent.glob('*.jpg'))
names={'503':'mouse','6e6':'power','706':'cup','a58':'earbuds','d9c':'camus','e57':'math'}
assets={names[p.name[:3]]:'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode() for p in photos}
items=[('mouse','无线鼠标｜浅蓝色，日常自用','65','九成新','小林'),('math','离散数学及其应用 第8版','28','八成新','陈同学'),('earbuds','Sanag S6S Pro 蓝牙耳机','89','九成新','阿禾'),('camus','加缪《西西弗神话》','15','八成新','书页'),('power','小米移动电源 黑色','40','八成新','木木'),('cup','玻璃吸管杯 520mL','12','全新','小夏')]
mx=ET.Element('mxfile',{'host':'app.diagrams.net','agent':'Codex','version':'24.7.17'})
pages=[]
class Screen:
 def __init__(self,name,title,admin=False):
  self.name=name;self.w=1280 if admin else 390;self.h=800 if admin else 844;self.svg=[];self.i=1
  dia=ET.SubElement(mx,'diagram',{'name':name,'id':name.split('_')[0]}); model=ET.SubElement(dia,'mxGraphModel',{'page':'1','pageWidth':str(self.w),'pageHeight':str(self.h),'background':BG});self.r=ET.SubElement(model,'root');ET.SubElement(self.r,'mxCell',{'id':'0'});ET.SubElement(self.r,'mxCell',{'id':'1','parent':'0'})
  self.rect(0,0,self.w,self.h,BG,0)
  if admin:
   self.rect(0,0,216,800,WHITE,0);self.text(24,45,'拾光 · 管理端',21,ACC,True);self.text(24,70,'CAMPUS MARKET',10,MUT)
   for j,t in enumerate(['工作概览','商品审核','商品管理','举报处理','交易争议','数据统计','操作日志']):
    yy=120+j*54
    if t in title:self.rect(12,yy-27,192,42,PALE,8)
    self.text(30,yy,t,15,ACC if t in title else MUT,t in title)
   self.text(24,750,'管理员 admin_demo',12,MUT);self.text(248,40,'管理工作台  /  '+title,13,MUT);self.text(248,84,title,26,INK,True);self.text(1060,40,'演示数据 · 2026-11-08',12,MUT)
  else:
   self.text(22,25,'9:41',13,INK,True);self.text(295,25,'▂ ▄ ▆   100%',11,INK)
   self.text(18,66,'‹' if name[:2]!='01' else '拾',27,ACC,True);self.text(50,64,title,19,INK,True)
 def cell(self,x,y,w,h,value,style):
  self.i+=1;c=ET.SubElement(self.r,'mxCell',{'id':str(self.i),'value':value,'style':style,'vertex':'1','parent':'1'});ET.SubElement(c,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})
 def rect(self,x,y,w,h,fill=WHITE,r=12,stroke=None):
  self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke or "none"}"/>')
  self.cell(x,y,w,h,'',f'rounded={int(r>0)};arcSize=12;fillColor={fill};strokeColor={stroke or "none"};')
 def text(self,x,y,t,size=14,color=INK,bold=False):
  self.svg.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">{html.escape(t)}</text>')
  self.cell(x,y-size, max(20,len(t)*size*.95),size*1.6,t,f'text;html=0;align=left;verticalAlign=top;spacing=0;fontFamily=Microsoft YaHei;fontSize={size};fontColor={color};fontStyle={int(bold)};strokeColor=none;fillColor=none;')
 def lines(self,x,y,lines,size=14,color=INK,gap=24):
  for i,t in enumerate(lines):self.text(x,y+i*gap,t,size,color)
 def image(self,key,x,y,w,h):
  uid=f'c{self.i}';data=assets[key]
  self.svg.append(f'<defs><clipPath id="{uid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9"/></clipPath></defs><image href="{data}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{uid})"/>')
  self.cell(x,y,w,h,'','shape=image;imageAspect=0;aspect=fixed;image='+data.replace(';base64,',',')+';')
 def button(self,x,y,w,t,primary=True):
  self.rect(x,y,w,44,ACC if primary else WHITE,10,None if primary else LINE);self.text(x+max(12,(w-len(t)*14)/2),y+28,t,14,WHITE if primary else ACC,True)
 def tag(self,x,y,t):self.rect(x,y, len(t)*11+16,23,PALE,5);self.text(x+8,y+16,t,11,ACC)
 def field(self,y,label,value,h=48):
  self.text(20,y,label,13,MUT);self.rect(16,y+12,358,h,WHITE,10,LINE);self.text(30,y+41,value,14)
 def nav(self,active='首页'):
  self.rect(0,776,390,68,WHITE,0,LINE)
  for i,(icon,t) in enumerate([('⌂','首页'),('+','发布'),('⇄','交易'),('○','我的')]):
   x=42+i*98;self.text(x,801,icon,24,ACC if t==active else MUT,True);self.text(x-3,824,t,11,ACC if t==active else MUT,t==active)
 def product(self,y,key='mouse',status=None):
  it=next(i for i in items if i[0]==key);self.rect(16,y,358,132);self.image(key,28,y+14,94,100);self.text(136,y+32,it[1][:15],13,INK,True);self.text(136,y+61,'¥ '+it[2],20,ACC,True);self.text(136,y+87,it[3]+' · '+it[4],12,MUT)
  if status:self.tag(136,y+98,status)
 def save(self,desc):
  data=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}"><g font-family="Microsoft YaHei, sans-serif">'+''.join(self.svg)+'</g></svg>'
  (SRC/(self.name+'.svg')).write_text(data,encoding='utf-8');pages.append({'name':self.name,'title':desc,'width':self.w,'height':self.h})

s=Screen('01_商品首页','校园拾光');s.text(287,62,'校园闲置',11,MUT);s.rect(16,88,358,44,WHITE,24,LINE);s.text(32,116,'⌕  搜索商品名称或描述',14,MUT)
for j,(a,b) in enumerate([('▣','数码'),('▤','书籍'),('◇','生活'),('○','运动')]):
 x=32+j*91;s.rect(x,151,52,44,PALE,14);s.text(x+17,180,a,22,ACC);s.text(x+12,216,b,12)
s.text(18,254,'校园好物',19,INK,True);s.text(251,254,'全部分类   筛选 ≡',12,MUT)
for j,it in enumerate(items[:4]):
 x=16+(j%2)*184;y=273+(j//2)*247;s.rect(x,y,174,235);s.image(it[0],x,y,174,144);s.text(x+10,y+164,it[1][:11],12,INK,True);s.text(x+10,y+187,'¥ '+it[2],19,ACC,True);s.text(x+100,y+186,it[3],10,MUT);s.text(x+10,y+216,'○ '+it[4]+'  ·  校园闲置',11,MUT)
s.nav();s.save('首页：搜索、分类与实拍商品卡片；只展示已发布可预约商品')

s=Screen('02_查询与筛选','筛选商品');s.field(104,'关键词','鼠标');s.field(201,'分类','数码  ▾');s.field(298,'价格区间','最低价  20          —          最高价  100');s.field(395,'商品状态','已发布 · 可预约');s.lines(22,508,['多个条件同时生效，按交集查询。','买家列表仅展示当前可预约的商品。'],12,MUT);s.button(16,608,110,'重置条件',False);s.button(138,608,236,'查看结果');s.rect(16,684,358,62,PALE);s.lines(28,708,['校验示例：最低价格不能高于最高价格。','保留输入内容，修改后可重新查询。'],12,ACC,22);s.save('组合筛选和非法价格区间提示')

s=Screen('03_商品详情','商品详情');s.text(328,64,'举报',13,MUT);s.image('mouse',0,84,390,292);s.tag(314,342,'1 / 1');s.text(20,415,'¥ 65',30,ACC,True);s.tag(284,393,'九成新');s.text(20,454,'无线鼠标｜浅蓝色，日常自用',18,INK,True);s.rect(16,477,358,66);s.text(30,503,'○  小林',14,INK,True);s.text(30,526,'卖家 · 普通账号',12,MUT);s.lines(20,578,['自用无线鼠标，外观如图。','功能正常，表面有轻微使用痕迹。','实际交付由双方在线下自行联系。'],14,INK,27);s.tag(20,673,'数码');s.tag(84,673,'已发布');s.text(20,733,'预约时保存价格，状态变化后会重新校验。',11,MUT);s.rect(0,766,390,78,WHITE,0,LINE);s.button(16,783,358,'预约商品');s.save('商品详情：实拍、价格、成色、卖家和预约入口')

s=Screen('04_预约确认','确认预约');s.product(96);s.rect(16,250,358,182);s.text(30,284,'请确认预约信息',17,INK,True);s.lines(30,321,['预约价格                         ¥ 65.00','商品状态                         已发布','交易方式                         线下自行交付'],13,INK,33);s.lines(22,472,['预约成功后，等待卖家确认。','此处不进行付款，不产生资金流水。','页面信息变化时，请刷新后重新确认。'],13,MUT,27);s.button(16,625,358,'确认以 ¥65 预约');s.text(20,697,'提交中会禁用按钮；服务端仍校验重复请求。',11,MUT);s.save('预约前明确价格；成功后生成价格快照')

s=Screen('05_登录','欢迎回到拾光');s.text(22,114,'让闲置，找到下一位主人。',15,MUT);s.field(167,'账号','请输入账号');s.field(270,'密码','请输入密码');s.button(16,407,358,'登录');s.button(16,467,358,'创建账号',False);s.text(22,557,'游客也可以浏览和查询商品。',13,MUT);s.text(22,587,'发布、预约和管理记录需要先登录。',12,MUT);s.rect(16,642,358,67,PALE);s.lines(29,668,['错误示例：账号或密码不正确。','请检查后重试，页面保留已输入的账号。'],12,ACC,23);s.save('登录表单、游客准入及失败提示')
s=Screen('06_注册','创建账号');s.field(112,'账号','设置唯一账号');s.field(208,'密码','设置登录密码');s.field(304,'确认密码','再次输入密码');s.rect(16,414,358,92,PALE);s.lines(28,441,['注册字段为设计暂定方案。','校内身份验证方式仍待确认，','本原型不展示“已认证”标识。'],12,ACC,23);s.button(16,548,358,'注册');s.text(20,641,'错误示例：该账号已存在，请更换账号。',12,ACC);s.save('注册暂定字段及账号重复提示')

s=Screen('07_发布与编辑','发布闲置');s.text(305,64,'存草稿',12,ACC);s.image('mouse',16,92,103,100);s.rect(130,92,103,100,WHITE,10,LINE);s.text(167,140,'+',28,MUT);s.text(150,171,'添加图片',12,MUT);s.field(227,'标题','无线鼠标｜浅蓝色，日常自用');s.field(323,'分类 / 成色','数码  ▾                       九成新  ▾');s.field(419,'价格（元）','65.00');s.field(515,'商品描述','请如实说明使用情况与瑕疵',90);s.text(20,664,'提交后进入审核，通过后才对买家公开。',12,MUT);s.button(16,710,110,'保存草稿',False);s.button(138,710,236,'提交审核');s.nav('发布');s.save('发布和编辑：图片、标题、分类、价格、成色、描述')

s=Screen('08_我的商品','我的商品');s.text(18,111,'全部    草稿    待审核    已发布',13,ACC,True);s.product(135,'mouse','已发布');s.button(136,280,106,'编辑',False);s.button(253,280,106,'下架',False);s.product(346,'earbuds','审核驳回');s.rect(16,490,358,92,PALE);s.lines(28,517,['驳回原因：请补充商品实际使用情况。','修改后可以重新提交审核。'],12,ACC,26);s.button(200,599,160,'修改并重新提交');s.text(20,701,'已预约或交易中商品：改价、删除、下架不可用。',11,MUT);s.nav('我的');s.save('卖家商品列表、审核反馈和状态操作限制')

for code,title,seller in [('09_买入预约','我买到的',False),('10_卖出预约','我卖出的',True)]:
 s=Screen(code,title);s.text(18,110,'全部   待确认   交易中   已完成',13,ACC,True);s.product(136,'mouse','待卖家确认');s.text(28,300,'预约价格 ¥65.00 · 记录 R20261108001',11,MUT)
 if seller:s.button(136,328,106,'拒绝',False);s.button(254,328,106,'接受预约')
 else:s.button(136,328,106,'取消预约',False);s.button(254,328,106,'查看详情')
 s.product(409,'math','已完成');s.text(28,570,'历史记录会保留，不因取消或拒绝而删除。',12,MUT);s.rect(16,620,358,80,PALE);s.lines(28,648,['仅在待卖家确认阶段允许普通取消或拒绝。','进入交易中后，有争议请联系管理员处理。'],12,ACC,25);s.nav('交易');s.save(title+'：状态筛选、价格快照与允许操作')

for code,title,buyer in [('11_交易详情_买家','交易详情',True),('12_交易详情_卖家','交易详情',False)]:
 s=Screen(code,title);s.rect(16,94,358,112,PALE);s.text(30,127,'待买家确认' if buyer else '交易中',23,ACC,True);s.text(30,158,'卖家已标记交付，请核对线下交付情况。' if buyer else '请在线下交付物品后再标记已交付。',12,ACC);s.text(30,184,'预约 → 卖家确认 → 交付 → 买家确认',11,MUT);s.product(226);s.rect(16,379,358,180);s.lines(30,409,['预约编号       R20261108001','预约价格       ¥65.00（创建时快照）','预约时间       2026-11-08 14:20','卖家确认       2026-11-08 14:25'],12,INK,36);s.lines(22,603,['确认完成后，商品和预约同时进入已完成。','仅卖家标记交付不能认定交易完成。'],12,MUT,26)
 if buyer:s.button(16,704,110,'提出争议',False);s.button(138,704,236,'确认交易完成')
 else:s.button(16,704,358,'标记已交付')
 s.save('买家确认完成与争议入口' if buyer else '卖家交付标记，不能代替买家确认')

for code,title,dispute in [('13_举报商品','举报商品',False),('14_提出争议','提出交易争议',True)]:
 s=Screen(code,title);s.product(96);s.field(273,'争议说明' if dispute else '举报原因','请描述具体情况，原因不能为空',140);s.rect(16,490,358,106,PALE);s.lines(28,519,['提交后由管理员介入并保留交易记录。','商品仍处于交易中，不能重新预约。','证据形式与处理时限待确认。'] if dispute else ['管理员会核查举报并记录处理结果。','原型仅展示提交结果，','暂不提供举报处理进度查询。'],12,ACC,26);s.button(16,650,358,'提交争议' if dispute else '提交举报');s.save('争议说明表单与处理边界' if dispute else '举报表单与提交反馈')

s=Screen('15_个人中心与统计','我的拾光');s.rect(16,100,358,100);s.text(34,140,'○  小林',23,INK,True);s.text(34,172,'一个账号，可以买也可以卖。',12,MUT)
for x,n,t in [(16,'6','商品总数'),(138,'2','已发布'),(260,'3','完成交易')]:s.rect(x,217,114,99);s.text(x+18,257,n,28,ACC,True);s.text(x+18,287,t,12,MUT)
s.text(20,350,'我的服务',17,INK,True)
for i,t in enumerate(['我发布的商品','我买到的 / 我卖出的','商品状态统计','退出登录']):s.rect(16,370+i*59,358,50);s.text(30,402+i*59,t,14);s.text(343,402+i*59,'›',18,MUT)
s.text(20,655,'草稿 1 · 待审核 1 · 已发布 2 · 已完成 2',11,MUT);s.text(20,684,'完成交易：本人卖出且预约状态为已完成的记录数。',10,MUT);s.nav('我的');s.save('个人中心、卖家商品状态统计与完成数量')

s=Screen('16_状态冲突反馈','操作结果');s.rect(16,140,358,244);s.text(39,192,'商品状态已变化',23,ACC,True);s.lines(39,234,['该商品已被其他买家预约。','本次未创建新的预约记录。','请刷新查看当前状态。'],14,INK,32);s.button(32,424,326,'刷新商品信息');s.button(32,485,326,'返回商品列表',False);s.rect(16,587,358,101,PALE);s.lines(29,617,['无结果时显示：暂无符合条件的商品。','提供“清空筛选”，不显示空白页面。','所有失败都保留必要输入并说明原因。'],12,ACC,25);s.save('并发或旧页面状态冲突、无结果反馈')

def panel(s,title,subtitle=''):
 s.rect(248,112,1000,64);s.text(268,150,title,14,INK,True)
 if subtitle:s.text(800,150,subtitle,12,MUT)
def table(s,headers,rows,widths=None):
 xs=widths or [268,430,720,910,1090];s.rect(248,194,1000,44,PALE,8)
 for x,t in zip(xs,headers):s.text(x,221,t,12,ACC,True)
 for j,row in enumerate(rows):
  y=238+j*64;s.rect(248,y,1000,62,WHITE,0)
  for x,t in zip(xs,row):s.text(x,y+37,t,12,ACC if x==xs[-1] else INK)

s=Screen('17_后台_商品审核','商品审核',True);panel(s,'待审核  3       已处理','关键词搜索     /     分类筛选');table(s,['商品编号','商品标题','卖家','状态','操作'],[['P1001','无线鼠标 浅蓝色','小林','待审核','查看审核'],['P1002','Sanag S6S Pro 耳机','阿禾','待审核','查看审核'],['P1003','小米移动电源','木木','待审核','查看审核']]);s.rect(248,461,1000,295);s.image('mouse',270,483,238,242);s.text(532,505,'无线鼠标｜浅蓝色，日常自用',20,INK,True);s.lines(532,539,['数码  /  九成新  /  ¥65.00','商品描述：功能正常，表面有轻微使用痕迹。','审核意见（驳回时必填）'],13,INK,33);s.rect(530,625,675,47,BG,8,LINE);s.text(546,655,'请输入原因，不直接修改卖家商品内容',12,MUT);s.button(906,693,140,'驳回',False);s.button(1060,693,140,'审核通过');s.save('审核列表和商品详情，驳回原因必填')

s=Screen('18_后台_商品管理','商品管理',True);panel(s,'关键词  无线鼠标     分类  数码     状态  全部','查询    /    重置');table(s,['商品编号','商品标题','发布者','当前状态','操作'],[['P1001','无线鼠标 浅蓝色','小林','已发布','下架 / 冻结'],['P1002','Sanag S6S Pro 耳机','阿禾','已预约','冻结'],['P1003','小米移动电源','木木','违规冻结','查看记录']]);s.rect(248,470,1000,240);s.text(272,510,'冻结商品 P1002',20,ACC,True);s.lines(272,548,['冻结原因：疑似违规商品，需进一步核查。','待确认设计：未进入交易时取消有效预约；已进入交易时转入待管理员处理。','冻结后的恢复路径待确认，不提供解冻入口。'],13,INK,30);s.button(1060,642,160,'确认冻结');s.save('管理端全状态查询、下架冻结及原因记录')

s=Screen('19_后台_举报处理','举报处理',True);panel(s,'待处理  2       已处理','按时间 / 商品筛选');table(s,['举报编号','举报商品','举报人','处理状态','操作'],[['RP1001','无线鼠标 浅蓝色','陈同学','待处理','查看'],['RP1002','玻璃吸管杯','小夏','已处理','查看记录']]);s.rect(248,411,1000,325);s.text(272,450,'举报详情 RP1001',20,INK,True);s.lines(272,489,['举报原因：商品描述与图片信息可能不符。','处理结果（必填）：请输入核查结论。','关联动作：记录结果 / 下架 / 冻结；状态变更同时留痕。'],13,INK,34);s.rect(270,597,930,49,BG,8,LINE);s.text(287,628,'填写处理结果后才能标记为已处理',12,MUT);s.button(1040,670,160,'保存处理结果');s.save('举报核查、处理结论及关联违规动作')

s=Screen('20_后台_交易争议','交易争议',True);panel(s,'待管理员处理','仅展示与争议有关的必要信息');table(s,['预约编号','商品','买家 / 卖家','状态','操作'],[['R20261108001','无线鼠标 浅蓝色','陈同学 / 小林','待管理员处理','查看详情']]);s.rect(248,340,1000,389);s.text(272,382,'交易记录与处理意见',20,INK,True);s.lines(272,423,['买家说明：对线下交付情况存在分歧，请管理员核查。','预约快照价格：¥65.00；商品状态：交易中。','保留预约及业务日志，处理意见追加保存。','证据形式、处理时限、强制结案权限尚未确认。'],14,INK,38);s.rect(270,588,930,55,BG,8,LINE);s.text(287,621,'填写处理意见；保存意见不会自动恢复商品或结束交易',13,MUT);s.button(1040,668,160,'保存处理意见');s.save('争议处理仅记录意见，保留历史，不擅自结案')

s=Screen('21_后台_数据统计','数据统计',True);panel(s,'时间范围  2026-11-01 至 2026-11-08     分类  全部     状态  全部','应用筛选')
for x,n,t in [(248,'24','商品数量'),(502,'12','预约记录'),(756,'6','完成数量'),(1010,'3 / 4','举报已处理 / 总数')]:s.rect(x,201,238,119);s.text(x+22,251,n,31,ACC,True);s.text(x+22,289,t,13,MUT)
s.rect(248,345,610,322);s.text(273,384,'商品状态分布',18,INK,True)
for j,(t,v) in enumerate([('已发布',8),('待审核',4),('已完成',6),('其他状态',6)]):
 y=423+j*50;s.text(274,y+17,t,12);s.rect(348,y,440,24,BG,4);s.rect(348,y,v*48,24,ACC if j==0 else '#B88B94',4);s.text(800,y+17,str(v),12)
s.rect(880,345,368,322);s.text(902,384,'统计口径',18,INK,True);s.lines(902,425,['所有数字为演示数据。','商品数：范围内创建的商品当前状态。','预约数：范围内创建的全部预约。','完成数：范围内完成的预约记录。','有效预约不含取消、拒绝、完成记录。','时间定义为暂定设计，待甲方确认。','无数据返回零；暂不提供导出。'],12,MUT,29);s.save('管理员筛选统计、状态分布和指标口径')

s=Screen('22_后台_操作日志','操作日志',True);panel(s,'时间范围    操作者    对象类型    操作类型','查询 / 重置');table(s,['操作时间','操作者 / 对象','操作','结果 / 状态变化','详情'],[['11-08 14:20','陈同学 / P1001','创建预约','成功 已发布→已预约','查看'],['11-08 14:25','小林 / R001','卖家确认','成功 待确认→交易中','查看'],['11-08 15:00','admin_demo / P1002','审核驳回','成功 待审核→驳回','查看'],['11-08 15:10','陈同学 / P1003','预约','失败 商品不可预约','查看']],[268,430,700,868,1170]);s.rect(248,555,1000,174);s.text(272,596,'操作记录详情',20,INK,True);s.lines(272,635,['包含操作者、时间、对象、动作、结果，以及状态变更前后值。','业务成功日志与业务事务一起落库；失败及越权请求另记安全日志。','管理端仅查询，不提供修改或删除日志；保留期限待确认。'],13,MUT,29);s.save('管理员日志筛选、状态前后值及安全事件')

ET.ElementTree(mx).write(SRC/'校园拾光_UI设计.drawio',encoding='utf-8',xml_declaration=True)
(SRC/'ui_manifest.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
(SRC/'UI工具说明.md').write_text('''# UI源稿说明

校园拾光采用diagrams.net兼容的原生XML设计稿，各页面中的文字、形状、图片均为独立对象。用 https://app.diagrams.net/ 打开“校园拾光_UI设计.drawio”可编辑。SVG保留矢量文字与内嵌实拍图片，也可导入Figma或Pixso继续设计。PNG是按源稿渲染的静态页面，并非真实运行的交易系统。

主色 #792D3C，背景 #F7F5F2，正文 #292529，辅助色 #777176。手机基准390×844，管理端1280×800；移动端正文12至18px，主要按钮44px高。首页屏幕内未展示全部商品，可滚动继续浏览；原型不承诺未确认的排序与分页规则。商品状态仅作文本说明，权限和准入由服务端独立验证。

六张照片由项目提供者实拍，未经AI替换；原型价格、账号、成色、时间为设计示例。原型未提供真实支付、物流、站内聊天、实名认证、收藏、评分或虚构成交量。UI22页覆盖主要功能和必要错误状态。
''',encoding='utf-8')
print('Created',len(pages),'editable screens')
