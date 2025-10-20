import type { GetStaticProps } from "next";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";
import type { OpinionItemOutput } from "@/client/types.gen";

interface HomeProps {
  opinions: OpinionItemOutput[];
  seasons: number[];
}

function formatCaseCaption(caption: string) {
  // Split on " v. " (with spaces) and render v. in italics, rest in small caps
  const parts = caption.split(/( v\. )/i);

  return (
    <>
      {parts.map((part, idx) => {
        if (part.match(/^ v\. $/i)) {
          return (
            <em key={idx} className="font-equity">
              {part}
            </em>
          );
        }
        return (
          <span key={idx} className="font-equity-caps">
            {part}
          </span>
        );
      })}
    </>
  );
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

export default function Home({ opinions, seasons }: HomeProps) {
  const router = useRouter();
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 25;

  // Initialize page from query params
  useEffect(() => {
    const pageParam = router.query.page;
    if (pageParam) {
      const page = parseInt(pageParam as string, 10);
      if (!Number.isNaN(page) && page > 0) {
        setCurrentPage(page);
      }
    }
  }, [router.query.page]);

  // Update query params when page changes
  useEffect(() => {
    if (currentPage === 1) {
      // Remove page param on page 1
      const { page: _page, ...rest } = router.query;
      router.replace({ pathname: router.pathname, query: rest }, undefined, {
        shallow: true,
      });
    } else {
      // Set page param for other pages
      router.replace(
        {
          pathname: router.pathname,
          query: { ...router.query, page: currentPage },
        },
        undefined,
        { shallow: true },
      );
    }
  }, [currentPage, router.pathname, router.query, router.replace]);

  // Filter opinions by selected season
  const filteredOpinions = useMemo(() => {
    if (selectedSeason === null) {
      return opinions;
    }
    return opinions.filter((opinion) => {
      const season = getSeason(opinion.case.episode.pub_date);
      return season === selectedSeason;
    });
  }, [opinions, selectedSeason]);

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
  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {/* Header */}
      <header className="text-center mb-12 border-b-2 border-accent pb-8">
        <h1 className="font-old-english text-6xl text-accent">Fantasy Court</h1>
      </header>

      {/* Opinions List Header with Season Filter */}
      <div className="flex items-center justify-between mb-6">
        <div className="font-equity-caps text-2xl text-foreground/90">
          Opinions
        </div>

        {/* Season Filter Dropdown */}
        <select
          value={selectedSeason ?? "all"}
          onChange={(e) =>
            handleSeasonChange(
              e.target.value === "all" ? null : parseInt(e.target.value),
            )
          }
          className="text-sm text-foreground/80 px-4 py-2 border border-border rounded-sm bg-background hover:border-accent transition-colors cursor-pointer"
        >
          <option value="all">All Seasons</option>
          {seasons.map((season) => (
            <option key={season} value={season}>
              {season}
            </option>
          ))}
        </select>
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
                  <h3 className="text-lg font-bold text-foreground mb-2">
                    {opinion.case.case_caption
                      ? formatCaseCaption(opinion.case.case_caption)
                      : "Untitled Case"}{" "}
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
                    className="text-base text-foreground/90 leading-relaxed"
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
                      (page === totalPages - 1 && currentPage < totalPages - 2);

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
