// Fantasy Court slip opinion, set as a half-letter booklet. The opinion
// arrives as JSON in sys.inputs.opinion, built by court/export/export_pdfs.py.
#let data = json(bytes(sys.inputs.opinion))

#let site = "https://fantasycourt.pages.dev"
#let accent = rgb("8b4513")
#let caps(body) = text(font: "Equity A Caps", body)
#let spaced-caps(body) = text(font: "Equity A Caps", tracking: 0.05em, body)
#let blackletter(body) = text(font: "OPTIEngraversOldEnglish", body)

// Inline runs: plain strings, or (kind, children) nodes from the opinion HTML.
#let render(node) = {
  if type(node) == str { return node }
  let body = node.children.map(render).join()
  if node.kind == "em" { emph(body) } else if node.kind == "b" {
    strong(body)
  } else if node.kind == "sc" { caps(body) } else if node.kind == "cite" {
    link(site + "/opinions/" + node.docket, text(fill: accent, body))
  } else { body }
}
#let inline(nodes) = nodes.map(render).join()

#let centered(body) = block(width: 100%, sticky: true)[
  #set par(first-line-indent: 0pt, justify: false, spacing: 0.62em)
  #set text(hyphenate: false)
  #align(center, body)
]

#let show-block(b) = {
  if b.kind == "p" { par(inline(b.children)) } else if b.kind == "part-header" {
    block(above: 1.6em, below: 1.1em, sticky: true, centered(inline(b.children)))
  } else if b.kind == "section-break" {
    block(above: 1.4em, below: 1.4em, centered[\* #h(0.8em) \* #h(0.8em) \*])
  } else if b.kind == "disposition" {
    block(above: 1.2em, width: 100%)[
      #set par(first-line-indent: 0pt, justify: false)
      #align(right, emph(inline(b.children)))
    ]
  } else if b.kind == "list" {
    enum(indent: 1.5em, body-indent: 0.6em, ..b.items.map(inline))
  }
}
#let show-blocks(blocks) = blocks.map(show-block).join()

// "HG v. Commissioner" in caps, with the "v." in italic lowercase.
#let caption-caps(caption) = caption.split(" v. ").map(caps).join([ #emph[v.] ])

#let short-rule = line(length: 3.5em, stroke: 0.5pt)

// Each opinion drops a marker so the running head knows whose pages these are.
#let segment(head) = [#metadata(head)<segment>]

#let running-header = context {
  let number = here().page()
  set text(size: 9.5pt)
  set par(first-line-indent: 0pt, justify: false, spacing: 0.62em)
  if number == 1 {
    grid(
      columns: (1fr, auto, 1fr),
      [(Slip Opinion)], spaced-caps(upper(data.term)), [],
    )
    return
  }
  let marks = query(<segment>).filter(m => m.location().page() <= number)
  let head = if marks.len() > 0 { marks.last().value } else { [] }
  grid(
    columns: (1fr, auto, 1fr),
    [], caption-caps(data.caption), align(right)[#number],
  )
  v(0.1em)
  align(center, head)
}

#set document(
  title: [#data.caption, No. #data.docket_number (#data.year)],
  author: "Fantasy Court",
)
#set page(
  width: 5.5in,
  height: 8.5in,
  margin: (x: 0.7in, top: 0.9in, bottom: 0.75in),
  header: running-header,
  header-ascent: 35%,
)
#set text(
  font: "Equity A",
  size: 10.5pt,
  lang: "en",
  region: "US",
  hyphenate: true,
)
#set par(justify: true, leading: 0.62em, spacing: 1.1em)
#show link: set text(hyphenate: false)

// The court name and caption that open every opinion.
#let caption-block(date: true) = {
  centered[
    #text(size: 22pt, blackletter[Fantasy Court])
    #v(0.2em)
    #short-rule
    #v(0.1em)
    No.~#data.docket_number
    #v(0.1em)
    #short-rule
    #v(0.4em)
    #text(size: 11.5pt, caption-caps(data.caption))
    #if data.procedural_posture != none {
      v(0.3em)
      text(size: 9.5pt, emph(data.procedural_posture))
    }
    #if date {
      v(0.3em)
      [\[#data.decided_date\]]
    }
  ]
  v(1.2em)
}

// Syllabus
#segment[Syllabus]
#centered[
  #spaced-caps[FANTASY COURT]
  #v(0.5em)
  #caps[Syllabus]
  #v(0.8em)
  #text(size: 11.5pt, caption-caps(data.caption))
  #if data.procedural_posture != none {
    v(0.3em)
    text(size: 9.5pt, emph(data.procedural_posture))
  }
  #v(0.5em)
  #text(size: 9.5pt)[
    No.~#data.docket_number.
    #if data.heard_date == none [
      Decided #data.decided_date
    ] else if data.heard_date == data.decided_date [
      Heard and decided #data.heard_date
    ] else [
      Heard #data.heard_date\u{2014}Decided #data.decided_date
    ]
  ]
  #if data.episode_title != none {
    v(0.1em)
    text(size: 8.5pt)[
      #emph[The Ringer Fantasy Football Show], #if data.segment_times == none [\u{201C}#data.episode_title\u{201D}] else [\u{201C}#data.episode_title,\u{201D} at #data.segment_times]
    ]
  }
]
#v(1em)

#show-blocks(data.facts)
#if data.questions.len() == 1 and data.questions.first().kind == "p" {
  par[#emph[Question presented:] #inline(data.questions.first().children)]
} else if data.questions.len() > 0 {
  par(emph[Questions presented:])
  show-blocks(data.questions)
}
#show-blocks(data.holding)
#show-blocks(data.reasoning)
#v(0.6em)
#show-blocks(data.authorship)

// Opinion of the Court
#pagebreak()
#segment(inline(data.majority_head))
#caption-block()
#show-blocks(data.authorship)
#show-blocks(data.majority)

// Concurrences and dissents, each on its own page like the slip opinions
#for opinion in data.separate {
  pagebreak()
  segment(inline(opinion.running_head))
  caption-block()
  par(inline(opinion.heading))
  show-blocks(opinion.blocks)
}
