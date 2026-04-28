import { execSync } from "node:child_process"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { Date as DateComponent, getDate } from "./Date"
import { byDateAndAlphabetical } from "./PageList"
import { FullSlug, resolveRelative } from "../util/path"

const DAY_MS = 24 * 60 * 60 * 1000
const GRID_WEEKS = 26

function dateKey(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function startOfDay(date: Date): Date {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

function getCommitCounts(): Map<string, number> {
  const today = startOfDay(new Date())
  const since = new Date(today.getTime() - (GRID_WEEKS * 7 - 1) * DAY_MS)

  try {
    const output = execSync(`git log --date=short --pretty=format:%ad --since=${dateKey(since)}`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    })

    const counts = new Map<string, number>()
    for (const day of output.split(/\r?\n/).filter(Boolean)) {
      counts.set(day, (counts.get(day) ?? 0) + 1)
    }
    return counts
  } catch {
    return new Map()
  }
}

function getGridDays(): Date[] {
  const today = startOfDay(new Date())
  const start = new Date(today.getTime() - (GRID_WEEKS * 7 - 1) * DAY_MS)
  const days: Date[] = []

  for (let i = 0; i < GRID_WEEKS * 7; i++) {
    days.push(new Date(start.getTime() + i * DAY_MS))
  }

  return days
}

function activityLevel(count: number): number {
  if (count === 0) return 0
  if (count === 1) return 1
  if (count <= 3) return 2
  if (count <= 6) return 3
  return 4
}

const HomeUpdates: QuartzComponent = ({ cfg, fileData, allFiles }: QuartzComponentProps) => {
  const latestPages = allFiles
    .filter((page) => {
      const slug = page.slug ?? ""
      const isFolderIndex = page.filePath?.endsWith("index.md") ?? false
      return slug !== "index" && !slug.startsWith("tags/") && !isFolderIndex
    })
    .sort(byDateAndAlphabetical(cfg))
    .slice(0, 6)

  const commitCounts = getCommitCounts()
  const gridDays = getGridDays()
  const totalCommits = [...commitCounts.values()].reduce((sum, count) => sum + count, 0)

  return (
    <section class="home-updates">
      <div class="home-updates-header">
        <h2>Latest Updates</h2>
        <a href={resolveRelative(fileData.slug!, "research-logs" as FullSlug)}>Research Logs</a>
      </div>

      <ul class="home-latest-list">
        {latestPages.map((page) => {
          const title = page.frontmatter?.title ?? page.slug
          const tags = page.frontmatter?.tags ?? []

          return (
            <li>
              <a href={resolveRelative(fileData.slug!, page.slug!)}>{title}</a>
              <span>
                {page.dates && <DateComponent date={getDate(cfg, page)!} locale={cfg.locale} />}
                {tags.length > 0 && ` · ${tags.slice(0, 2).join(", ")}`}
              </span>
            </li>
          )
        })}
      </ul>

      <div class="home-activity">
        <div class="home-activity-title">
          <h2>Activity</h2>
          <span>
            {totalCommits} commits in the last {GRID_WEEKS} weeks
          </span>
        </div>
        <div class="activity-grid" aria-label="Git commit activity">
          {gridDays.map((day) => {
            const key = dateKey(day)
            const count = commitCounts.get(key) ?? 0
            return (
              <span
                class={`activity-cell level-${activityLevel(count)}`}
                title={`${key}: ${count} commit${count === 1 ? "" : "s"}`}
              />
            )
          })}
        </div>
        <div class="activity-legend" aria-hidden="true">
          <span>Less</span>
          {[0, 1, 2, 3, 4].map((level) => (
            <i class={`activity-cell level-${level}`} />
          ))}
          <span>More</span>
        </div>
      </div>
    </section>
  )
}

HomeUpdates.css = `
.home-updates {
  margin-top: 2.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--lightgray);
}

.home-updates h2 {
  margin: 0;
  font-size: 1.2rem;
}

.home-updates-header,
.home-activity-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.home-updates-header > a,
.home-activity-title > span,
.home-latest-list span,
.activity-legend {
  color: var(--darkgray);
  font-size: 0.9rem;
}

.home-latest-list {
  list-style: none;
  margin: 0 0 2rem;
  padding: 0;
}

.home-latest-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) max-content;
  gap: 1rem;
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--lightgray);
}

.home-latest-list a {
  background: transparent;
}

.activity-grid {
  display: grid;
  grid-auto-flow: column;
  grid-template-rows: repeat(7, 10px);
  grid-auto-columns: 10px;
  gap: 4px;
  width: max-content;
  max-width: 100%;
  overflow-x: auto;
  padding-bottom: 0.25rem;
}

.activity-cell {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: var(--lightgray);
}

.activity-cell.level-1 {
  background: #9be9a8;
}

.activity-cell.level-2 {
  background: #40c463;
}

.activity-cell.level-3 {
  background: #30a14e;
}

.activity-cell.level-4 {
  background: #216e39;
}

.activity-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
  margin-top: 0.5rem;
}

@media (max-width: 800px) {
  .home-updates-header,
  .home-activity-title,
  .home-latest-list li {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
}
`

export default (() => HomeUpdates) satisfies QuartzComponentConstructor
