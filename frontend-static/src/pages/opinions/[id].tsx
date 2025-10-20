import type { GetStaticPaths, GetStaticProps } from "next";
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

  // Create a mapping from docket number to opinion ID
  const docketToIdMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const citedCase of opinion.case.cases_cited) {
      if (citedCase.opinion) {
        map.set(citedCase.docket_number, citedCase.opinion.id);
      }
    }
    return map;
  }, [opinion.case.cases_cited]);

  // Convert citation spans to anchor tags after component mounts
  useEffect(() => {
    const citationSpans = document.querySelectorAll("[data-cite-docket]");
    const anchors: HTMLAnchorElement[] = [];

    citationSpans.forEach((span) => {
      const docket = span.getAttribute("data-cite-docket");
      if (docket && docketToIdMap.has(docket)) {
        const opinionId = docketToIdMap.get(docket);

        // Wrap the span in an anchor tag
        const anchor = document.createElement("a");
        anchor.href = `/opinions/${opinionId}`;
        anchor.className =
          "text-accent hover:underline transition-colors cursor-pointer";
        anchor.setAttribute("aria-label", `Link to cited case ${docket}`);

        // Replace span with anchor containing the span's content
        const parent = span.parentNode;
        if (parent) {
          anchor.innerHTML = span.innerHTML;
          anchor.setAttribute("data-cite-docket", docket);
          parent.replaceChild(anchor, span);
          anchors.push(anchor);
        }
      }
    });

    // Handle clicks for client-side navigation
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const anchor = target.closest("a[data-cite-docket]") as HTMLAnchorElement;

      if (anchor) {
        e.preventDefault();
        const href = anchor.getAttribute("href");
        if (href) {
          router.push(href);
        }
      }
    };

    document.addEventListener("click", handleClick);

    return () => {
      document.removeEventListener("click", handleClick);
    };
  }, [docketToIdMap, router]);

  const handleCopyCitation = async () => {
    const year = new Date(opinion.case.episode.pub_date).getFullYear();
    const citation = `${opinion.case.case_caption || "Untitled Case"}, No. ${opinion.case.docket_number} (${year})`;

    await navigator.clipboard.writeText(citation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
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
      <article className="space-y-6">
        {/* Holding */}
        <div className="bg-accent/5 border-l-4 border-accent p-6 pt-4 pb-4 mb-8 rounded-r">
          <div
            className="text-base leading-relaxed"
            dangerouslySetInnerHTML={{ __html: opinion.holding_statement_html }}
          />
        </div>

        {/* Authorship */}
        <div
          className="text-base text-foreground/80"
          dangerouslySetInnerHTML={{ __html: opinion.authorship_html }}
        />

        {/* Opinion Body */}
        <div
          className="opinion-body text-base leading-relaxed mt-4"
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
  );
}

export const getStaticPaths: GetStaticPaths = async () => {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");

  const indexPath = path.join(process.cwd(), "public", "data", "index.json");

  let opinions: Array<{ id: number }> = [];

  try {
    const data = await fs.readFile(indexPath, "utf-8");
    opinions = JSON.parse(data);
  } catch (error) {
    console.error("Failed to load opinions index:", error);
  }

  const paths = opinions.map((opinion) => ({
    params: { id: opinion.id.toString() },
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
