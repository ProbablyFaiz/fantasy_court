import type { GetStaticPaths, GetStaticProps } from "next";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";
import type { OpinionRead } from "@/client/types.gen";
import CaseAudioPlayer from "@/components/AudioPlayer";

interface OpinionPageProps {
  opinion: OpinionRead;
}

function formatCaseCaption(caption: string) {
  // Split on " v. " (with spaces) and wrap v. in italics, rest in small caps
  // Need to handle HTML entities from smartypants
  const formatted = caption.replace(
    /( v\. )/gi,
    '<em class="font-equity">$1</em>',
  );

  return `<span class="font-equity-caps">${formatted}</span>`;
}

export default function OpinionPage({ opinion }: OpinionPageProps) {
  const router = useRouter();
  const [copied, setCopied] = useState(false);

  // Helper function to strip HTML tags for meta descriptions
  const stripHtml = (html: string) => {
    return html
      .replace(/<[^>]*>/g, "")
      .replace(/&[^;]+;/g, " ")
      .trim();
  };

  // Create title and description for meta tags
  const pageTitle = opinion.case.case_caption
    ? `${opinion.case.case_caption} - Fantasy Court`
    : "Opinion - Fantasy Court";
  const pageDescription = stripHtml(opinion.holding_statement_html).substring(
    0,
    155,
  );
  const opinionUrl = `https://fantasycourt.lexeme.dev/opinions/${opinion.case.docket_number}`;

  // Create a set of docket numbers that have opinions (for citation linking)
  const validCitationDockets = useMemo(() => {
    const dockets = new Set<string>();
    for (const citedCase of opinion.case.cases_cited) {
      if (citedCase.opinion) {
        dockets.add(citedCase.docket_number);
      }
    }
    return dockets;
  }, [opinion.case.cases_cited]);

  // Convert citation spans to anchor tags after component mounts
  useEffect(() => {
    const opinionBody = document.querySelector(".opinion-body");
    if (!opinionBody) return;

    const citationSpans = opinionBody.querySelectorAll("[data-cite-docket]");

    citationSpans.forEach((span) => {
      const docket = span.getAttribute("data-cite-docket");
      if (docket && validCitationDockets.has(docket)) {
        // Skip if this is already an anchor tag
        if (span.tagName.toLowerCase() === "a") {
          return;
        }

        // Wrap the span in an anchor tag
        const anchor = document.createElement("a");

        anchor.href = `/opinions/${docket}`;
        anchor.className =
          "text-accent hover:underline transition-colors cursor-pointer";
        anchor.setAttribute("aria-label", `Link to cited case ${docket}`);

        // Replace span with anchor containing the span's content
        const parent = span.parentNode;
        if (parent) {
          anchor.innerHTML = span.innerHTML;
          anchor.setAttribute("data-cite-docket", docket);
          parent.replaceChild(anchor, span);
        }
      }
    });

    // Handle clicks for client-side navigation - only within opinion body
    const handleClick = (e: Event) => {
      const target = e.target as HTMLElement;
      const anchor = target.closest("a[data-cite-docket]") as HTMLAnchorElement;

      if (anchor?.hasAttribute("data-cite-docket")) {
        e.preventDefault();
        e.stopPropagation();
        const href = anchor.getAttribute("href");
        if (href?.startsWith("/opinions/")) {
          router.push(href);
        }
      }
    };

    opinionBody.addEventListener("click", handleClick);

    return () => {
      opinionBody.removeEventListener("click", handleClick);
    };
  }, [validCitationDockets, router]);

  const handleCopyCitation = async () => {
    const year = new Date(opinion.case.episode.pub_date).getFullYear();
    const citation = `${opinion.case.case_caption || "Untitled Case"}, No. ${opinion.case.docket_number} (${year})`;

    await navigator.clipboard.writeText(citation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      <Head>
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
        <meta property="og:title" content={pageTitle} />
        <meta property="og:description" content={pageDescription} />
        <meta property="og:type" content="article" />
        <meta property="og:url" content={opinionUrl} />
        <meta
          property="article:published_time"
          content={opinion.case.episode.pub_date}
        />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={pageTitle} />
        <meta name="twitter:description" content={pageDescription} />
      </Head>
      <div className="max-w-2xl mx-auto px-6 py-12">
        {/* Header with back link */}
        <div className="mb-8">
          <Link
            href="/"
            className="font-equity-caps text-sm text-accent hover:underline"
          >
            ← Back to Opinions
          </Link>
        </div>

        {/* Case Header */}
        <header className="mb-8 pb-8 border-b-2 border-accent">
          <h1 className="text-2xl font-bold text-foreground mb-4">
            {opinion.case.case_caption ? (
              <span
                dangerouslySetInnerHTML={{
                  __html: formatCaseCaption(opinion.case.case_caption),
                }}
              />
            ) : (
              "Untitled Case"
            )}{" "}
            ({new Date(opinion.case.episode.pub_date).getFullYear()})
          </h1>

          <div className="text-base text-foreground/70 space-y-2">
            <div className="font-equity-caps">
              No. {opinion.case.docket_number}
            </div>
            <div>
              <em>{opinion.case.episode.title}</em> (
              {new Date(opinion.case.episode.pub_date).toLocaleDateString(
                "en-US",
                {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                },
              )}
              )
            </div>

            {/* Audio Player */}
            {opinion.case.episode.bucket_mp3_public_url && (
              <div className="mt-2">
                <CaseAudioPlayer
                  audioUrl={opinion.case.episode.bucket_mp3_public_url}
                  startTime={opinion.case.start_time_s}
                  endTime={opinion.case.end_time_s}
                  episodeTitle={opinion.case.episode.title}
                />
              </div>
            )}
          </div>
        </header>

        {/* Opinion Content */}
        <article>
          {/* Procedural Posture */}
          {opinion.case.procedural_posture && (
            <div className="text-sm text-foreground/70 pb-4 mb-4 border-b border-border/30">
              <span className="font-equity-caps text-foreground/80">
                Procedural Posture:
              </span>{" "}
              {opinion.case.procedural_posture}
            </div>
          )}

          {/* Holding */}
          <div className="bg-accent/5 border-l-4 border-accent p-6 pt-4 pb-2 mb-8 rounded-r">
            <div
              className="text-base leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: opinion.holding_statement_html,
              }}
            />
          </div>

          {/* Authorship */}
          <div
            className="text-base text-foreground/80 mb-6"
            dangerouslySetInnerHTML={{ __html: opinion.authorship_html }}
          />

          {/* Opinion Body */}
          <div
            className="opinion-body text-base leading-relaxed"
            dangerouslySetInnerHTML={{ __html: opinion.opinion_body_html }}
          />

          {/* Citation */}
          <div className="mt-12 pt-8 border-t border-border">
            <div className="text-sm text-foreground/60 mb-2">
              <span className="font-equity-caps">Cite as:</span>{" "}
              {opinion.case.case_caption ? (
                <em
                  className="font-equity"
                  dangerouslySetInnerHTML={{
                    __html: opinion.case.case_caption,
                  }}
                />
              ) : (
                <em className="font-equity">Untitled Case</em>
              )}
              , No. {opinion.case.docket_number} (
              {new Date(opinion.case.episode.pub_date).getFullYear()})
              <button
                onClick={handleCopyCitation}
                className="ml-3 text-accent hover:text-accent/80 transition-colors font-equity-caps text-xs"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Topics */}
          {opinion.case.case_topics && opinion.case.case_topics.length > 0 && (
            <div className="mt-6">
              <div className="font-equity-caps text-sm text-foreground/60 mb-3">
                Topics
              </div>
              <div className="flex flex-wrap gap-2">
                {opinion.case.case_topics.map((topic, idx) => (
                  <span
                    key={idx}
                    className="font-equity-caps text-xs px-2 py-1 bg-accent/10 text-accent rounded-sm"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}
        </article>
      </div>
    </>
  );
}

export const getStaticPaths: GetStaticPaths = async () => {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");

  const indexPath = path.join(process.cwd(), "public", "data", "index.json");

  let opinions: Array<{ case: { docket_number: string } }> = [];

  try {
    const data = await fs.readFile(indexPath, "utf-8");
    opinions = JSON.parse(data);
  } catch (error) {
    console.error("Failed to load opinions index:", error);
  }

  const paths = opinions.map((opinion) => ({
    params: { id: opinion.case.docket_number },
  }));

  return {
    paths,
    fallback: false,
  };
};

export const getStaticProps: GetStaticProps<OpinionPageProps> = async ({
  params,
}) => {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");

  const opinionPath = path.join(
    process.cwd(),
    "public",
    "data",
    "opinions",
    `${params?.id}.json`,
  );

  let opinion: OpinionRead | null = null;

  try {
    const data = await fs.readFile(opinionPath, "utf-8");
    opinion = JSON.parse(data);
  } catch (error) {
    console.error(`Failed to load opinion ${params?.id}:`, error);
  }

  if (!opinion) {
    return {
      notFound: true,
    };
  }

  return {
    props: {
      opinion,
    },
  };
};
