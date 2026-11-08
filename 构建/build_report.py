from pathlib import Path
import re,json,html
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parents[1]
try:
 pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
except Exception:
 pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light')); 'fallback'
 CN='STSong-Light'
else: CN='CN'
W,H=A4; WIDTH=W-88
styles={
 'p':ParagraphStyle('p',fontName=CN,fontSize=10.2,leading=17,spaceAfter=8,wordWrap='CJK'),
 'h1':ParagraphStyle('h1',fontName=CN,fontSize=16,leading=23,spaceBefore=15,spaceAfter=11,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName=CN,fontSize=12,leading=19,spaceBefore=10,spaceAfter=7,keepWithNext=True),
 'small':ParagraphStyle('small',fontName=CN,fontSize=8.5,leading=13,spaceAfter=5,wordWrap='CJK'),
 'title':ParagraphStyle('title',fontName=CN,fontSize=27,leading=40,alignment=TA_CENTER,spaceAfter=25),
 'cap':ParagraphStyle('cap',fontName=CN,fontSize=10,leading=16,alignment=TA_CENTER,spaceAfter=10),
}
def P(t,k='p'):
 t=html.escape(t);t=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',t)
 return Paragraph(t,styles[k])
story=[]
story += [Spacer(1,92),P('软件工程实践 实验二','cap'),P('校内二手交易系统\n面向对象设计'.replace('\n',' '),'title'),P('校园拾光','cap'),Spacer(1,35),P('姓名：待填写    学号：待填写','cap'),P('日期：2026年11月8日','cap'),Spacer(1,45),P('项目范围：校园闲置物品的信息、审核、预约及线下交付状态管理。','p'),P('交付内容：实验报告、PlantUML源码与图、用户端和管理端UI原型。','p'),P('版本：'+('代理审查修订版' if (ROOT/'协作记录/03_代理审查与修订.md').exists() else 'AI生成初稿'),'p'),PageBreak()]

def markdown(text):
 lines=text.splitlines();i=0
 while i<len(lines):
  line=lines[i].strip();i+=1
  if not line:continue
  if line.startswith('|'):
   rows=[]
   while True:
    vals=[v.strip() for v in line.strip('|').split('|')]
    if not all(re.fullmatch(r'[-: ]+',v or '-') for v in vals):rows.append(vals)
    if i>=len(lines) or not lines[i].strip().startswith('|'):break
    line=lines[i].strip();i+=1
   n=len(rows[0]);widths=([96,WIDTH-96] if n==2 else [75,(WIDTH-75)*.48,(WIDTH-75)*.52])
   if n!=len(widths):widths=[WIDTH/n]*n
   t=Table([[P(v,'small') for v in r] for r in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
   t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EEE8E9')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#B9ADB0')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#FAF9F7')])]))
   story.extend([t,Spacer(1,12)]);continue
  if line.startswith('# '):continue
  if line.startswith('## '):story.append(P(line[3:],'h1'));continue
  if line.startswith('### '):story.append(P(line[4:],'h2'));continue
  story.append(P(line))

markdown((ROOT/'设计源稿/系统设计初稿.md').read_text(encoding='utf-8'))
story.append(PageBreak());story.append(P('附录一 UML设计图','h1'))
explain={
 'UML类图':'结构性图。以账号、商品、预约为核心，显示字段、行为、基数及服务依赖。数据库实施约束另见正文第五章。',
 'UML组件图':'结构性图。模块化单体分层，业务服务协调领域与仓储。图片文件和数据库分别存储。',
 'UML用例图':'行为性图。游客、普通用户和管理员按权限参与；买卖角色共享普通账号。',
 'UML活动图':'行为性图。覆盖商品草稿、审核、预约、线下交付与买家确认；突出责任交接。',
 'UML商品状态图':'行为性图。九种商品状态；冻结和恢复的待确认路径显式标注。',
 'UML预约状态图':'行为性图。预约七种状态；争议入口与终态有别，不虚构处理出口。',
 'UML时序图':'交互性图。鉴权、幂等、商品锁、价格版本、快照及同步写入在一个事务内协调。',
}
for j,(stem,desc) in enumerate(explain.items()):
 if j:story.append(PageBreak())
 story.append(P(stem,'h2'));story.append(P(desc))
 file=ROOT/'UML'/(stem+'.png')
 if file.exists():
  iw,ih=PILImage.open(file).size;r=min(WIDTH/iw,620/ih);story.append(Image(str(file),iw*r,ih*r));story.append(Spacer(1,9));story.append(P('图 '+str(j+1)+'  '+stem+'。同名源码和高清PNG见UML目录。','cap'))
 else:story.append(P('初稿源码已保存，图像待渲染。'))

story.append(PageBreak());story.append(P('附录二 UI界面与功能','h1'));story.append(P('原型提供22张界面。手机端390×844、管理端1280×800，PNG按2倍像素导出。可编辑设计稿见设计源稿目录。截图内所有交易数据均为演示。'))
manifest=json.loads((ROOT/'设计源稿/ui_manifest.json').read_text(encoding='utf-8'))
mobile=[p for p in manifest if p['width']<500];admins=[p for p in manifest if p['width']>=500]
for start in range(0,len(mobile),2):
 if start:story.append(PageBreak())
 pair=mobile[start:start+2];cells=[]
 for p in pair:
  iw,ih=PILImage.open(ROOT/'UI界面'/(p['name']+'.png')).size;r=min(232/iw,510/ih)
  cells.append([P(p['name'].replace('_',' '),'h2'),Image(str(ROOT/'UI界面'/(p['name']+'.png')),iw*r,ih*r),Spacer(1,9),P(p['title'],'small')])
 if len(cells)==1:cells.append([])
 t=Table([cells],colWidths=[WIDTH/2,WIDTH/2]);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),8)]));story.append(t)
for start in range(0,len(admins),2):
 story.append(PageBreak())
 for p in admins[start:start+2]:
  story.append(P(p['name'].replace('_',' '),'h2'));iw,ih=PILImage.open(ROOT/'UI界面'/(p['name']+'.png')).size;r=WIDTH/iw
  story.extend([Image(str(ROOT/'UI界面'/(p['name']+'.png')),iw*r,ih*r),Spacer(1,7),P(p['title'],'small'),Spacer(1,10)])

story.append(PageBreak());story.append(P('附录三 AI协作原始记录','h1'))
for p in sorted((ROOT/'协作记录').glob('*.md')):
 story.append(P(p.stem,'h2'));markdown(p.read_text(encoding='utf-8'))

def footer(c,d):
 c.saveState();c.setFont(CN,8);c.setFillColor(colors.HexColor('#777176'));c.drawString(44,24,'校园拾光  面向对象设计');c.drawRightString(W-44,24,str(d.page));c.restoreState()
doc=SimpleDocTemplate(str(ROOT/'实验报告.pdf'),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=38,bottomMargin=42,title='校内二手交易系统面向对象设计实验报告',author='校园拾光项目')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print('PDF built',ROOT/'实验报告.pdf')
