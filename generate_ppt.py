import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_presentation(output_path="P_and_ID_Line_Tool_Client_Presentation.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5) # 16:9 Widescreen
    blank_layout = prs.slide_layouts[6]

    # Color Palette matching presentation.html & web app
    NAVY = RGBColor(15, 23, 42)          # #0f172a - Dark primary background
    CARD_DARK = RGBColor(30, 41, 59)     # #1e293b - Dark card fill
    TEAL = RGBColor(14, 165, 233)        # #0ea5e9 - Primary accent teal
    BLUE = RGBColor(59, 130, 246)        # #3b82f6 - Accent blue
    GREEN = RGBColor(16, 185, 129)       # #10b981 - Success accent green
    PURPLE = RGBColor(139, 92, 246)      # #8b5cf6 - Accent purple
    RED = RGBColor(239, 68, 68)          # #ef4444 - Warning accent red
    AMBER = RGBColor(245, 158, 11)       # #f59e0b - Accent amber
    WHITE = RGBColor(255, 255, 255)
    TEXT_LIGHT = RGBColor(248, 250, 252) # #f8fafc
    TEXT_MUTED = RGBColor(148, 163, 184) # #94a3b8
    BORDER_COLOR = RGBColor(51, 65, 85)  # #334155

    def set_slide_background(slide, color):
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_header(slide, title_text, category_text):
        # Category Badge
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        tf_cat.margin_left = tf_cat.margin_top = tf_cat.margin_right = tf_cat.margin_bottom = 0
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = TEAL
        p_cat.font.name = "Inter"

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11.7), Inches(0.8))
        tf_t = title_box.text_frame
        tf_t.word_wrap = True
        tf_t.margin_left = tf_t.margin_top = tf_t.margin_right = tf_t.margin_bottom = 0
        p_t = tf_t.paragraphs[0]
        p_t.text = title_text
        p_t.font.size = Pt(28)
        p_t.font.bold = True
        p_t.font.color.rgb = WHITE
        p_t.font.name = "Inter"

    def add_card(slide, left, top, width, height, bg_color=CARD_DARK, border_color=BORDER_COLOR):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = bg_color
        if border_color:
            shape.line.color.rgb = border_color
            shape.line.width = Pt(1.5)
        else:
            shape.line.fill.background()
        return shape

    def set_speaker_notes(slide, notes_text):
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes_text

    # =============================================================
    # SLIDE 1: Title Slide (Cover)
    # =============================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide1, NAVY)

    # Accent decorative bar
    bar = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.5), Inches(0.12), Inches(4.2))
    bar.fill.solid()
    bar.fill.fore_color.rgb = TEAL
    bar.line.fill.background()

    # Title text box
    tbox = slide1.shapes.add_textbox(Inches(1.1), Inches(1.5), Inches(11.4), Inches(2.2))
    tf1 = tbox.text_frame
    tf1.word_wrap = True
    
    p0 = tf1.paragraphs[0]
    p0.text = "NEXT-GEN ENGINEERING AUTOMATION"
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = TEAL
    p0.font.name = "Inter"

    p1 = tf1.add_paragraph()
    p1.text = "P&ID Line List Tool"
    p1.font.size = Pt(44)
    p1.font.bold = True
    p1.font.color.rgb = WHITE
    p1.font.name = "Inter"

    p2 = tf1.add_paragraph()
    p2.text = "AI-Driven Automated Extraction, Line Naming Philosophy Parsing & Standardized Excel Segregation"
    p2.font.size = Pt(18)
    p2.font.color.rgb = TEXT_MUTED
    p2.font.name = "Inter"
    p2.space_before = Pt(10)

    # 3 Feature Cards
    cards_data1 = [
        ("⚡ 10x Faster Segregation", "Converts multi-day manual line list data entry into an automated process under 2 minutes.", TEAL),
        ("🤖 AI Philosophy Engine", "Parses ANY custom line-numbering specification (Aramco, Shell, BP, EPC standards) dynamically.", PURPLE),
        ("📄 Direct P&ID PDF OCR", "Extracts line tags directly from engineering PDF drawing packages into master Excel templates.", BLUE)
    ]
    for idx, (ctitle, cdesc, ccolor) in enumerate(cards_data1):
        left_pos = Inches(1.1 + idx * 3.8)
        card_s = add_card(slide1, left_pos, Inches(4.0), Inches(3.6), Inches(2.7), CARD_DARK, ccolor)
        
        cbox = slide1.shapes.add_textbox(left_pos + Inches(0.2), Inches(4.2), Inches(3.2), Inches(2.3))
        ctf = cbox.text_frame
        ctf.word_wrap = True
        
        cp1 = ctf.paragraphs[0]
        cp1.text = ctitle
        cp1.font.size = Pt(18)
        cp1.font.bold = True
        cp1.font.color.rgb = WHITE
        cp1.font.name = "Inter"

        cp2 = ctf.add_paragraph()
        cp2.text = cdesc
        cp2.font.size = Pt(14)
        cp2.font.color.rgb = TEXT_MUTED
        cp2.font.name = "Inter"
        cp2.space_before = Pt(8)

    set_speaker_notes(slide1, "SLIDE 1 (Title): Welcome clients. Introduce the P&ID Line List Tool as an enterprise solution built specifically for EPC contractors, process engineers, and plant designers to automate line list segregation.")

    # =============================================================
    # SLIDE 2: Market Challenge (Manual vs Automated)
    # =============================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide2, NAVY)
    add_header(slide2, "The Bottleneck in P&ID Line List Management", "MARKET CHALLENGE")

    # Left Card (Manual Process)
    add_card(slide2, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0), RGBColor(30, 20, 30), RED)
    mbox = slide2.shapes.add_textbox(Inches(1.1), Inches(2.0), Inches(5.0), Inches(4.6))
    mtf = mbox.text_frame
    mtf.word_wrap = True
    
    mp1 = mtf.paragraphs[0]
    mp1.text = "⚠️ Traditional Manual Process"
    mp1.font.size = Pt(20)
    mp1.font.bold = True
    mp1.font.color.rgb = RED
    
    m_items = [
        ("🔴 Tedious Manual Entry", "Engineers spend 20+ hours reading P&ID drawings and typing line tags into spreadsheets."),
        ("🔴 Inconsistent Conventions", "Projects use conflicting line formats (Fluid-Seq-Size vs Size-Fluid-Class)."),
        ("🔴 High Error Rates", "Typographical errors in line size or pipe class trigger expensive downstream piping re-work.")
    ]
    for title, desc in m_items:
        p_t = mtf.add_paragraph()
        p_t.text = title
        p_t.font.size = Pt(15)
        p_t.font.bold = True
        p_t.font.color.rgb = WHITE
        p_t.space_before = Pt(14)
        
        p_d = mtf.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(13)
        p_d.font.color.rgb = TEXT_MUTED

    # Right Card (Automated Solution)
    add_card(slide2, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0), RGBColor(15, 35, 30), GREEN)
    abox = slide2.shapes.add_textbox(Inches(7.1), Inches(2.0), Inches(5.1), Inches(4.6))
    atf = abox.text_frame
    atf.word_wrap = True
    
    ap1 = atf.paragraphs[0]
    ap1.text = "✅ Automated Solution"
    ap1.font.size = Pt(20)
    ap1.font.bold = True
    ap1.font.color.rgb = GREEN
    
    a_items = [
        ("🟢 Instant Automated Parsing", "Segregates Fluid Code, Sequence No, Size, Class & Insulation instantly under 2 seconds."),
        ("🟢 Universal AI Adaptability", "Simply type plain-English philosophy rules to handle any client standard dynamically."),
        ("🟢 Standardized Output", "Direct population of official Linelist_reference master Excel templates.")
    ]
    for title, desc in a_items:
        p_t = atf.add_paragraph()
        p_t.text = title
        p_t.font.size = Pt(15)
        p_t.font.bold = True
        p_t.font.color.rgb = WHITE
        p_t.space_before = Pt(14)
        
        p_d = atf.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(13)
        p_d.font.color.rgb = TEXT_MUTED

    set_speaker_notes(slide2, "SLIDE 2 (Problem): Highlight client pain points. Manual data entry takes 20+ hours per project, leads to transcription errors in pipe classes/sizes, and causes expensive re-work.")

    # =============================================================
    # SLIDE 3: Core Platform Capabilities
    # =============================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide3, NAVY)
    add_header(slide3, "Core Platform Capabilities", "PLATFORM OVERVIEW")

    pillars = [
        ("📊 Excel Line Segregation", "Parses raw line strings into structured columns with styled master cell formatting.", TEAL),
        ("🎛️ AI Philosophy Profiles", "Save, manage, and toggle between Aramco, BP, Shell, or custom project specs.", PURPLE),
        ("👁️ P&ID Drawing OCR", "Extracts line tags directly from vector/raster CAD drawing PDF packages.", BLUE),
        ("📑 M&N & Batch Merge", "Apply Material & Numbering rules and merge multi-P&ID lists into master documents.", GREEN)
    ]
    for idx, (ctitle, cdesc, ccolor) in enumerate(pillars):
        left_pos = Inches(0.8 + idx * 2.95)
        add_card(slide3, left_pos, Inches(1.8), Inches(2.75), Inches(5.0), CARD_DARK, ccolor)
        
        cbox = slide3.shapes.add_textbox(left_pos + Inches(0.2), Inches(2.1), Inches(2.35), Inches(4.4))
        ctf = cbox.text_frame
        ctf.word_wrap = True
        
        cp1 = ctf.paragraphs[0]
        cp1.text = ctitle
        cp1.font.size = Pt(18)
        cp1.font.bold = True
        cp1.font.color.rgb = ccolor
        cp1.font.name = "Inter"

        cp2 = ctf.add_paragraph()
        cp2.text = cdesc
        cp2.font.size = Pt(14)
        cp2.font.color.rgb = TEXT_MUTED
        cp2.font.name = "Inter"
        cp2.space_before = Pt(14)

    set_speaker_notes(slide3, "SLIDE 3 (Capabilities): Walk through the 4 core pillars: Excel Segregation, AI Line Philosophy Profiles, PDF Drawing OCR, and M&N Batch Merging.")

    # =============================================================
    # SLIDE 4: AI Line Philosophy Engine
    # =============================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide4, NAVY)
    add_header(slide4, "AI Line Philosophy Engine", "DEEP DIVE")

    # Left Column Text Box
    lbox = slide4.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    ltf = lbox.text_frame
    ltf.word_wrap = True
    
    lp0 = ltf.paragraphs[0]
    lp0.text = "Zero Code Configuration"
    lp0.font.size = Pt(22)
    lp0.font.bold = True
    lp0.font.color.rgb = TEAL
    
    lp1 = ltf.add_paragraph()
    lp1.text = "Traditional regex software breaks when client line conventions change. Our AI Philosophy Engine lets engineers write plain-English rules or paste client line spec sheets directly into the web app."
    lp1.font.size = Pt(14)
    lp1.font.color.rgb = TEXT_MUTED
    lp1.space_before = Pt(10)

    lp2 = ltf.add_paragraph()
    lp2.text = "Interactive Live Preview"
    lp2.font.size = Pt(16)
    lp2.font.bold = True
    lp2.font.color.rgb = WHITE
    lp2.space_before = Pt(16)

    lp3 = ltf.add_paragraph()
    lp3.text = "Test sample line strings against your philosophy before running 100+ page PDF drawing packages."
    lp3.font.size = Pt(13)
    lp3.font.color.rgb = TEXT_MUTED

    lp4 = ltf.add_paragraph()
    lp4.text = "Local Fallback Protection"
    lp4.font.size = Pt(16)
    lp4.font.bold = True
    lp4.font.color.rgb = GREEN
    lp4.space_before = Pt(16)

    lp5 = ltf.add_paragraph()
    lp5.text = "Zero-API key local rule engine guarantees high performance even in offline environments."
    lp5.font.size = Pt(13)
    lp5.font.color.rgb = TEXT_MUTED

    # Right Code Box
    add_card(slide4, Inches(6.7), Inches(1.8), Inches(5.8), Inches(5.0), RGBColor(10, 14, 26), BORDER_COLOR)
    rbox = slide4.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.2), Inches(4.6))
    rtf = rbox.text_frame
    rtf.word_wrap = True
    
    code_lines = [
        ("// Define Philosophy Profile", RGBColor(100, 116, 139)),
        ('"Aramco-Standard": {', RGBColor(244, 63, 94)),
        ('  "delimiter": "-",', RGBColor(56, 189, 248)),
        ('  "rules": "Fluid - Seq - Size - Class - Ins"', RGBColor(56, 189, 248)),
        ('}', RGBColor(244, 63, 94)),
        ("", WHITE),
        ("// Sample Input Tag", RGBColor(100, 116, 139)),
        ('"HPS-120816-50-A5-H"', RGBColor(250, 204, 21)),
        ("", WHITE),
        ("// Extracted Structured Output", RGBColor(100, 116, 139)),
        ('{', GREEN),
        ('  "Fluid Code": "HPS",', GREEN),
        ('  "Sequence No": "120816",', GREEN),
        ('  "Line Size (mm)": "50",', GREEN),
        ('  "Pipe Class": "A5", "Insulation": "H"', GREEN),
        ('}', GREEN)
    ]
    for idx, (cline, ccolor) in enumerate(code_lines):
        cp = rtf.paragraphs[0] if idx == 0 else rtf.add_paragraph()
        cp.text = cline
        cp.font.size = Pt(12)
        cp.font.name = "Consolas"
        cp.font.color.rgb = ccolor

    set_speaker_notes(slide4, "SLIDE 4 (AI Philosophy): Emphasize zero-code configuration. Show how easy it is to define plain-English rules for Aramco, BP, Shell, or custom project standards.")

    # =============================================================
    # SLIDE 5: 5-Step Automated Execution Workflow
    # =============================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide5, NAVY)
    add_header(slide5, "5-Step Automated Execution", "WORKFLOW")

    steps = [
        ("01", "Upload Files", "Upload raw Excel line list or P&ID PDF drawings.", TEAL),
        ("02", "Select Philosophy", "Pick saved profile or define custom line rules.", BLUE),
        ("03", "AI Extraction", "OCR & LLM engine segregates tags instantly.", PURPLE),
        ("04", "M&N Rules", "Configure fluid-specific material parameters.", GREEN),
        ("05", "Export Master", "Download populated reference template.", AMBER)
    ]
    for idx, (snum, stitle, sdesc, scolor) in enumerate(steps):
        left_pos = Inches(0.8 + idx * 2.36)
        add_card(slide5, left_pos, Inches(1.8), Inches(2.2), Inches(5.0), CARD_DARK, scolor)
        
        sbox = slide5.shapes.add_textbox(left_pos + Inches(0.15), Inches(2.1), Inches(1.9), Inches(4.4))
        stf = sbox.text_frame
        stf.word_wrap = True
        
        sp0 = stf.paragraphs[0]
        sp0.text = snum
        sp0.font.size = Pt(36)
        sp0.font.bold = True
        sp0.font.color.rgb = scolor
        
        sp1 = stf.add_paragraph()
        sp1.text = stitle
        sp1.font.size = Pt(16)
        sp1.font.bold = True
        sp1.font.color.rgb = WHITE
        sp1.space_before = Pt(10)

        sp2 = stf.add_paragraph()
        sp2.text = sdesc
        sp2.font.size = Pt(12)
        sp2.font.color.rgb = TEXT_MUTED
        sp2.space_before = Pt(8)

    set_speaker_notes(slide5, "SLIDE 5 (Workflow): Explain the simple 5-step user experience from raw upload to final standardized Linelist_reference master export.")

    # =============================================================
    # SLIDE 6: Enterprise Architecture & Security
    # =============================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide6, NAVY)
    add_header(slide6, "Architecture & Security", "ENTERPRISE READY")

    sec_items = [
        ("🖥️ Flexible Deployment", "Supports Docker containers, Google Cloud Run, Vercel Serverless, or local enterprise intranet servers.", TEAL),
        ("☁️ GCS Persistence", "Optional Google Cloud Storage integration for secure master template storage and signed URL downloads.", BLUE),
        ("🛡️ Data Privacy & Security", "Session isolation, HTTPS encryption, zero permanent file retention policies, protecting proprietary drawings.", PURPLE)
    ]
    for idx, (ctitle, cdesc, ccolor) in enumerate(sec_items):
        left_pos = Inches(0.8 + idx * 3.95)
        add_card(slide6, left_pos, Inches(1.8), Inches(3.7), Inches(5.0), CARD_DARK, ccolor)
        
        cbox = slide6.shapes.add_textbox(left_pos + Inches(0.25), Inches(2.2), Inches(3.2), Inches(4.2))
        ctf = cbox.text_frame
        ctf.word_wrap = True
        
        cp1 = ctf.paragraphs[0]
        cp1.text = ctitle
        cp1.font.size = Pt(20)
        cp1.font.bold = True
        cp1.font.color.rgb = ccolor

        cp2 = ctf.add_paragraph()
        cp2.text = cdesc
        cp2.font.size = Pt(14)
        cp2.font.color.rgb = TEXT_MUTED
        cp2.space_before = Pt(14)

    set_speaker_notes(slide6, "SLIDE 6 (Architecture & Security): Reassure client security leads: HTTPS encryption, session isolation, Docker/Cloud Run deployment, and zero permanent data retention option.")

    # =============================================================
    # SLIDE 7: Quantifiable ROI for Clients
    # =============================================================
    slide7 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide7, NAVY)
    add_header(slide7, "Quantifiable ROI for Clients", "BUSINESS IMPACT")

    stats = [
        ("95%", "Time Reduction per Line List", TEAL),
        ("100%", "Client Standard Compliance", GREEN),
        ("0", "Human Transcription Errors", PURPLE),
        ("10x", "Faster Bid & Proposal Turnaround", AMBER)
    ]
    for idx, (val, lbl, scolor) in enumerate(stats):
        left_pos = Inches(0.8 + idx * 2.95)
        add_card(slide7, left_pos, Inches(2.0), Inches(2.75), Inches(4.5), CARD_DARK, scolor)
        
        sbox = slide7.shapes.add_textbox(left_pos + Inches(0.2), Inches(2.4), Inches(2.35), Inches(3.8))
        stf = sbox.text_frame
        stf.word_wrap = True
        
        sp0 = stf.paragraphs[0]
        sp0.text = val
        sp0.font.size = Pt(54)
        sp0.font.bold = True
        sp0.font.color.rgb = scolor
        sp0.alignment = PP_ALIGN.CENTER

        sp1 = stf.add_paragraph()
        sp1.text = lbl
        sp1.font.size = Pt(16)
        sp1.font.bold = True
        sp1.font.color.rgb = WHITE
        sp1.alignment = PP_ALIGN.CENTER
        sp1.space_before = Pt(16)

    set_speaker_notes(slide7, "SLIDE 7 (ROI): Present concrete ROI: 95% time savings, 100% compliance, zero human errors, and 10x faster proposal turnaround.")

    # =============================================================
    # SLIDE 8: Call to Action (Next Steps)
    # =============================================================
    slide8 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide8, NAVY)
    add_header(slide8, "Transform Your Piping Engineering Workflow", "NEXT STEPS & DEMONSTRATION")

    add_card(slide8, Inches(1.8), Inches(1.8), Inches(9.7), Inches(5.0), CARD_DARK, TEAL)
    cbox8 = slide8.shapes.add_textbox(Inches(2.2), Inches(2.2), Inches(8.9), Inches(4.2))
    ctf8 = cbox8.text_frame
    ctf8.word_wrap = True

    cp0 = ctf8.paragraphs[0]
    cp0.text = "🤝 Schedule a Live Demonstration"
    cp0.font.size = Pt(28)
    cp0.font.bold = True
    cp0.font.color.rgb = WHITE
    cp0.alignment = PP_ALIGN.CENTER

    cp1 = ctf8.add_paragraph()
    cp1.text = "Let us demonstrate the P&ID Line List Tool live on your proprietary drawing packages and custom line philosophy standards."
    cp1.font.size = Pt(16)
    cp1.font.color.rgb = TEXT_MUTED
    cp1.alignment = PP_ALIGN.CENTER
    cp1.space_before = Pt(14)

    cp2 = ctf8.add_paragraph()
    cp2.text = "🚀 Launch Web Application: http://127.0.0.1:5001"
    cp2.font.size = Pt(20)
    cp2.font.bold = True
    cp2.font.color.rgb = TEAL
    cp2.alignment = PP_ALIGN.CENTER
    cp2.space_before = Pt(30)

    set_speaker_notes(slide8, "SLIDE 8 (CTA): Invite the client for a live hands-on proof-of-concept using their sample P&ID drawings and custom line philosophy templates.")

    prs.save(output_path)
    print(f"Presentation saved successfully to {output_path}")

if __name__ == "__main__":
    create_presentation()
