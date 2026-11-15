"""Build a printable handbook from the numbered editable Markdown documents."""
from pathlib import Path
import re
import textwrap
from xml.sax.saxutils import escape
from _bootstrap import ROOT
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Preformatted,KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents


def inline(text):
    text=escape(text)
    text=re.sub(r"\[([^]]+)\]\((https?://[^)]+)\)",lambda m:f'<link href="{m[2]}" color="#1A3B5C">{m[1]}</link>',text)
    text=re.sub(r"\[([^]]+)\]\([^)]+\)",r"\1",text)
    text=re.sub(r"\*\*(.+?)\*\*",r"<b>\1</b>",text)
    text=re.sub(r"`([^`]+)`",r'<font name="Courier" size="8">\1</font>',text)
    return text


class Handbook(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and hasattr(flowable,"bookmark_key"):
            key=flowable.bookmark_key
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(),key,level=0)
            self.notify("TOCEntry",(0,flowable.getPlainText(),self.page,key))


def main():
    font_pairs=[(Path("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf"),Path("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf")),(Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf")),(Path("C:/Windows/Fonts/arial.ttf"),Path("C:/Windows/Fonts/arialbd.ttf")),
                (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))]
    pair=next((p for p in font_pairs if all(f.is_file() for f in p)),None)
    if pair is None: raise FileNotFoundError("Install Arial or DejaVu Sans to build the handbook")
    for name,file in zip(("ResearchBody","ResearchBold"),pair):
        pdfmetrics.registerFont(TTFont(name,str(file)))
    pdfmetrics.registerFontFamily("ResearchBody",normal="ResearchBody",bold="ResearchBold",italic="ResearchBody",boldItalic="ResearchBold")
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyResearch",fontName="ResearchBody",fontSize=10,leading=14,
        textColor=colors.black,spaceAfter=7,wordWrap="CJK",allowWidows=0,allowOrphans=0))
    styles.add(ParagraphStyle(name="DocTitle",fontName="ResearchBold",fontSize=21,leading=26,spaceAfter=15,textColor=colors.black))
    styles.add(ParagraphStyle(name="SectionResearch",fontName="ResearchBold",fontSize=13,leading=17,spaceBefore=13,spaceAfter=7,keepWithNext=True,textColor=colors.black))
    styles.add(ParagraphStyle(name="CellResearch",fontName="ResearchBody",fontSize=8.5,leading=12,spaceAfter=0,wordWrap="CJK"))
    styles.add(ParagraphStyle(name="TOCResearch",fontName="ResearchBody",fontSize=10,leading=18,leftIndent=0,firstLineIndent=0,spaceBefore=3))
    body=styles["BodyResearch"]; story=[]
    story.append(Paragraph("DREAM Project Handbook",styles["DocTitle"]))
    story.append(Paragraph("David Cook | Research release V1.3.1 | October 30 2026",body))
    story.append(Paragraph("A controlled research program for exploratory inference and reversible adapter learning. This handbook collects the rewritten papers, protocol, safeguards, attribution plan, run instructions, and measured test evidence.",body))
    story.append(Paragraph("Concept-association and reasoning revision. Current implementation, qualification evidence, exploratory results and proposed concept-learning work are distinguished throughout.",body))
    story.append(Paragraph("Contents",styles["SectionResearch"]))
    toc=TableOfContents(); toc.levelStyles=[styles["TOCResearch"]]; story.append(toc)
    def table(lines):
        rows=[[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
        rows=[r for r in rows if not all(re.fullmatch(r":?-+:?",c.replace(" ","")) for c in r)]
        columns=len(rows[0]); widths=([140,364] if columns==2 else [150,175,179] if columns==3 else [504/columns]*columns)
        data=[[Paragraph(inline(c),styles["CellResearch"]) for c in row] for row in rows]
        result=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT")
        result.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.45,colors.HexColor("#D9D9D9")),
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E6EBEF")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
        return result
    for number,path in enumerate(sorted((ROOT/"documents").glob("[0-9][0-9]-*.md")),1):
        story.append(PageBreak()); lines=path.read_text(encoding="utf-8").splitlines(); i=0
        while i<len(lines):
            line=lines[i]
            if not line.strip(): i+=1; continue
            if line.startswith("# "):
                p=Paragraph(f"{number:02d} {inline(line[2:])}",styles["DocTitle"]); p.bookmark_key=f"document-{number}"; story.append(p); i+=1
            elif line.startswith("## ") and path.name.startswith("12-"):
                # A source's author/title, status, and method credit travel together.
                group=[Paragraph(inline(line[3:]),styles["SectionResearch"])];i+=1
                while i<len(lines) and not lines[i].startswith("## "):
                    if not lines[i].strip(): i+=1;continue
                    paragraph=[lines[i]];i+=1
                    while i<len(lines) and lines[i].strip() and not lines[i].startswith("## "):
                        paragraph.append(lines[i]);i+=1
                    group.append(Paragraph(inline(" ".join(paragraph)),body))
                story.append(KeepTogether(group))
            elif line.startswith("## "):
                story.append(Paragraph(inline(line[3:]),styles["SectionResearch"])); i+=1
            elif line.startswith("```"):
                i+=1; code=[]
                while i<len(lines) and not lines[i].startswith("```"):
                    code+=textwrap.wrap(lines[i],width=96,replace_whitespace=False,drop_whitespace=False,subsequent_indent="  ") or [""]
                    i+=1
                story.append(Preformatted("\n".join(code),ParagraphStyle(name="CodeBlock",fontName="Courier",fontSize=8.4,leading=11,spaceAfter=7)))
                i+=1
            elif line.startswith("|"):
                group=[]
                while i<len(lines) and lines[i].startswith("|"):group.append(lines[i]);i+=1
                # Short chunks let a long literature table start beside its
                # introduction rather than pushing a whole table to a new page.
                if len(group)>9:
                    header=group[:2];rows=group[2:]
                    for start in range(0,len(rows),6):
                        story.append(table(header+rows[start:start+6]));story.append(Spacer(1,5))
                else:
                    story.append(table(group));story.append(Spacer(1,9))
            elif line.startswith("- "):
                story.append(Paragraph("- "+inline(line[2:]),body));i+=1
            else:
                group=[line];i+=1
                while i<len(lines) and lines[i].strip() and not lines[i].startswith(("#","|","```","- ")):
                    group.append(lines[i]);i+=1
                story.append(Paragraph(inline(" ".join(group)),body))
    output=ROOT/"handbook"/"DREAM-Project-Handbook-V1.3.1.pdf"; output.parent.mkdir(exist_ok=True)
    def footer(canvas,doc):
        canvas.setFont("ResearchBody",8);canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(54,30,"DREAM V1.3.1 | David Cook | Computational research prototype")
        canvas.drawRightString(558,30,str(doc.page))
    doc=Handbook(str(output),pagesize=(612,792),leftMargin=54,rightMargin=54,topMargin=49,bottomMargin=48,
                 title="DREAM Project Handbook V1.3.1",author="David Cook")
    doc.multiBuild(story,onFirstPage=footer,onLaterPages=footer)
    print(output)


if __name__=="__main__":main()
