import type { GetStaticProps } from "next";
import Head from "next/head";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { OpinionItemOutput } from "@/client/types.gen";
import { Select, SelectItem } from "@/components/Select";

interface HomeProps {
  opinions: OpinionItemOutput[];
  seasons: number[];
}

function formatCaseCaption(caption: string) {
  // Split on " v. " (with spaces) and wrap v. in italics, rest in small caps
  // Need to handle HTML entities from smartypants
  const formatted = caption.replace(
    /( v\. )/gi,
    '<em class="font-equity">$1</em>',
  );

  return `<em class="font-equity">${formatted}</em>`;
}

// Calculate season based on pub_date
// Season year is determined by the June 1 cutoff (June 1, 2025 - May 31, 2026 is "2025 season")
function getSeason(pubDate: string): number {
  const date = new Date(pubDate);
  const year = date.getFullYear();
  const month = date.getMonth(); // 0-indexed (0 = January, 5 = June)

  // If before June (month < 5), belongs to previous season
  return month < 5 ? year - 1 : year;
}

const STORAGE_KEY = "fantasy-court-filters";

export default function Home({ opinions, seasons }: HomeProps) {
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [opinionType, setOpinionType] = useState<
    "all" | "unanimous" | "divided"
  >("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Load saved filters from sessionStorage on mount
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const {
          selectedSeason: savedSeason,
          opinionType: savedType,
          searchQuery: savedSearch,
          currentPage: savedPage,
        } = JSON.parse(saved);
        if (savedSeason !== undefined) setSelectedSeason(savedSeason);
        if (savedType) setOpinionType(savedType);
        if (savedSearch) setSearchQuery(savedSearch);
        if (savedPage) setCurrentPage(savedPage);
      }
    } catch (error) {
      // Ignore errors from parsing invalid JSON
      console.error("Failed to load saved filters:", error);
    }
  }, []);

  // Save filters to sessionStorage whenever they change
  useEffect(() => {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          selectedSeason,
          opinionType,
          searchQuery,
          currentPage,
        }),
      );
    } catch (error) {
      // Ignore storage errors (e.g., in incognito mode)
      console.error("Failed to save filters:", error);
    }
  }, [selectedSeason, opinionType, searchQuery, currentPage]);

  // Helper to strip HTML tags for searching
  const stripHtml = (html: string | null) => {
    if (!html) return "";
    return html
      .replace(/<[^>]*>/g, "")
      .replace(/&[^;]+;/g, " ")
      .trim();
  };

  // Filter opinions by selected season, opinion type, and search query
  const filteredOpinions = useMemo(() => {
    return opinions.filter((opinion) => {
      // Season filter
      if (selectedSeason !== null) {
        const season = getSeason(opinion.case.episode.pub_date);
        if (season !== selectedSeason) return false;
      }

      // Opinion type filter
      if (opinionType !== "all") {
        const hasDissentMention = opinion.authorship_html
          .toLowerCase()
          .includes("dissent");
        if (opinionType === "unanimous" && hasDissentMention) return false;
        if (opinionType === "divided" && !hasDissentMention) return false;
      }

      // Search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const searchableText = [
          opinion.case.case_caption,
          opinion.case.docket_number,
          opinion.case.fact_summary,
          stripHtml(opinion.case.questions_presented_html),
          opinion.case.procedural_posture,
          opinion.case.case_topics?.join(" "),
          opinion.case.episode.title,
          stripHtml(opinion.case.episode.description_html),
          stripHtml(opinion.authorship_html),
          stripHtml(opinion.holding_statement_html),
          stripHtml(opinion.reasoning_summary_html),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        if (!searchableText.includes(query)) return false;
      }

      return true;
    });
  }, [opinions, selectedSeason, opinionType, searchQuery]);

  // Paginate filtered opinions
  const totalPages = Math.ceil(filteredOpinions.length / itemsPerPage);
  const paginatedOpinions = useMemo(() => {
    const startIdx = (currentPage - 1) * itemsPerPage;
    return filteredOpinions.slice(startIdx, startIdx + itemsPerPage);
  }, [filteredOpinions, currentPage]);

  const handleSeasonChange = (season: number | null) => {
    setSelectedSeason(season);
    setCurrentPage(1); // Reset to first page when filter changes
  };

  const handleOpinionTypeChange = (type: "all" | "unanimous" | "divided") => {
    setOpinionType(type);
    setCurrentPage(1); // Reset to first page when filter changes
  };

  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    setCurrentPage(1); // Reset to first page when search changes
  };
  return (
    <>
      <Head>
        <title>Fantasy Court</title>
        <meta
          name="description"
          content="Browse judicial opinions from the Fantasy Court podcast, the premier authority on fantasy football disputes and league controversies. Written opinions on trades, roster management, commissioner powers, and league rules."
        />
        <meta
          property="og:title"
          content="Fantasy Court - Judicial Opinions from the Fantasy Football Podcast"
        />
        <meta
          property="og:description"
          content="Browse judicial opinions from the Fantasy Court podcast, the premier authority on fantasy football disputes and league controversies."
        />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://fantasycourt.lexeme.dev/" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta
          name="twitter:title"
          content="Fantasy Court - Judicial Opinions from the Fantasy Football Podcast"
        />
        <meta
          name="twitter:description"
          content="Browse judicial opinions from the Fantasy Court podcast, the premier authority on fantasy football disputes and league controversies."
        />
      </Head>
      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Header */}
        <header className="text-center mb-12 border-b-2 border-accent pb-8">
          <h1 className="font-old-english text-6xl text-accent">
            Fantasy Court
          </h1>
        </header>

        {/* Opinions List Header with Filters */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="font-equity-caps text-2xl text-foreground/90">
              Opinions
            </div>

            <div className="flex gap-3">
              {/* Opinion Type Filter Dropdown */}
              <Select
                value={opinionType}
                onValueChange={(value) =>
                  handleOpinionTypeChange(
                    value as "all" | "unanimous" | "divided",
                  )
                }
              >
                <SelectItem value="all">All Opinions</SelectItem>
                <SelectItem value="unanimous">Unanimous</SelectItem>
                <SelectItem value="divided">Divided</SelectItem>
              </Select>

              {/* Season Filter Dropdown */}
              <Select
                value={selectedSeason?.toString() ?? "all"}
                onValueChange={(value) =>
                  handleSeasonChange(value === "all" ? null : parseInt(value))
                }
              >
                <SelectItem value="all">All Seasons</SelectItem>
                {seasons.map((season) => (
                  <SelectItem key={season} value={season.toString()}>
                    {season}
                  </SelectItem>
                ))}
              </Select>
            </div>
          </div>

          {/* Search Bar */}
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search opinions by caption, topics, holdings, facts..."
            className="w-full text-sm text-foreground/80 px-4 py-2 border border-border rounded-sm bg-background hover:border-accent focus:border-accent focus:outline-none transition-colors"
          />
        </div>

        {filteredOpinions.length === 0 ? (
          <div className="text-center py-16 text-foreground/60">
            <p>No opinions match the selected filters.</p>
          </div>
        ) : (
          <>
            <div className="space-y-8">
              {paginatedOpinions.map((opinion) => (
                <Link
                  key={opinion.id}
                  href={`/opinions/${opinion.id}`}
                  className="block border border-border hover:border-accent transition-colors duration-200 bg-background hover:bg-accent/5 p-6 rounded-sm"
                >
                  <article>
                    {/* Case Caption */}
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      {opinion.case.case_caption ? (
                        <span
                          dangerouslySetInnerHTML={{
                            __html: formatCaseCaption(
                              opinion.case.case_caption,
                            ),
                          }}
                        />
                      ) : (
                        "Untitled Case"
                      )}{" "}
                      ({new Date(opinion.case.episode.pub_date).getFullYear()})
                    </h3>

                    {/* Docket Number and Episode */}
                    <div className="text-sm text-foreground/70 mb-4 space-y-1">
                      <div className="font-equity-caps">
                        No. {opinion.case.docket_number}
                      </div>
                      <div>
                        <em>{opinion.case.episode.title}</em> (
                        {new Date(
                          opinion.case.episode.pub_date,
                        ).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        })}
                        )
                      </div>
                    </div>

                    {/* Authorship */}
                    <div
                      className="text-base text-foreground/80 mb-3"
                      dangerouslySetInnerHTML={{
                        __html: opinion.authorship_html,
                      }}
                    />

                    {/* Holding Statement */}
                    <div
                      className="bg-accent/5 border-l-4 border-accent p-4 rounded-r text-base leading-relaxed"
                      dangerouslySetInnerHTML={{
                        __html: opinion.holding_statement_html,
                      }}
                    />
                  </article>
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-12 flex items-center justify-center gap-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="px-4 py-2 font-equity-caps text-sm border border-border rounded-sm hover:bg-accent/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>

                <div className="flex gap-1">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                    (page) => {
                      // Show first page, last page, current page, and pages around current
                      const showPage =
                        page === 1 ||
                        page === totalPages ||
                        Math.abs(page - currentPage) <= 1;

                      const showEllipsis =
                        (page === 2 && currentPage > 3) ||
                        (page === totalPages - 1 &&
                          currentPage < totalPages - 2);

                      if (showEllipsis) {
                        return (
                          <span
                            key={page}
                            className="px-3 py-2 font-equity-caps text-sm"
                          >
                            ...
                          </span>
                        );
                      }

                      if (!showPage) return null;

                      return (
                        <button
                          key={page}
                          onClick={() => setCurrentPage(page)}
                          className={`px-3 py-2 font-equity-caps text-sm border rounded-sm transition-colors ${
                            currentPage === page
                              ? "bg-accent text-background border-accent"
                              : "border-border hover:bg-accent/10"
                          }`}
                        >
                          {page}
                        </button>
                      );
                    },
                  )}
                </div>

                <button
                  onClick={() =>
                    setCurrentPage((p) => Math.min(totalPages, p + 1))
                  }
                  disabled={currentPage === totalPages}
                  className="px-4 py-2 font-equity-caps text-sm border border-border rounded-sm hover:bg-accent/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

export const getStaticProps: GetStaticProps<HomeProps> = async () => {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");

  const dataPath = path.join(process.cwd(), "public", "data", "index.json");

  let opinions: OpinionItemOutput[] = [];

  try {
    const data = await fs.readFile(dataPath, "utf-8");
    opinions = JSON.parse(data);
  } catch (error) {
    console.error("Failed to load opinions:", error);
  }

  // Calculate all unique seasons from opinions
  const seasonsSet = new Set<number>();
  opinions.forEach((opinion) => {
    const season = getSeason(opinion.case.episode.pub_date);
    seasonsSet.add(season);
  });

  // Sort seasons in descending order (newest first)
  const seasons = Array.from(seasonsSet).sort((a, b) => b - a);

  return {
    props: {
      opinions,
      seasons,
    },
  };
};
