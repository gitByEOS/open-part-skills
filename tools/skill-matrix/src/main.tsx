import { StrictMode, useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import { createRoot } from "react-dom/client";
import "./styles/base.css";
import "./styles/theme-dark.css";

import { fetchShowcaseDocument } from "./fetch-document";
import { showcaseItems } from "./showcase-items";
import type { ShowcaseItem, ShowcaseType } from "./types";

type CardTagValue = NonNullable<ShowcaseItem["tag"]>;
type SparkleStyle = CSSProperties & { "--sparkle-scale": number };

const tagSparkleBaseAngles = [-25, 25, 155, 205];
const tagSparkleRadius = 20;
const tagSparkleJitter = 14;
const tagSparkleMinScale = 1.05;
const tagSparkleScaleRange = 0.45;
const sparklePresetCount = 20;

const showcaseTypeConfig = {
  skill: { label: "技能" },
  mcp: { label: "MCP" },
} satisfies Record<ShowcaseType, { label: string }>;

function getTypeLabel(type: ShowcaseType) {
  return showcaseTypeConfig[type].label;
}

function getCardVisualType(type: ShowcaseType) {
  return type === "mcp" ? "rule" : type;
}

function getSparkleStyle(baseAngle: number): SparkleStyle {
  const angle = baseAngle + (Math.random() * 2 - 1) * tagSparkleJitter;
  const radians = (angle * Math.PI) / 180;

  return {
    left: `calc(50% + ${Math.cos(radians) * tagSparkleRadius}px)`,
    top: `calc(50% + ${Math.sin(radians) * tagSparkleRadius}px)`,
    "--sparkle-scale": tagSparkleMinScale + Math.random() * tagSparkleScaleRange,
  };
}

const sparklePresets = Array.from({ length: sparklePresetCount }, () => {
  return tagSparkleBaseAngles.map((angle) => getSparkleStyle(angle));
});

function getRandomSparklePresetIndex(previousIndex?: number) {
  if (sparklePresets.length <= 1) {
    return 0;
  }

  let nextIndex = Math.floor(Math.random() * sparklePresets.length);
  while (nextIndex === previousIndex) {
    nextIndex = Math.floor(Math.random() * sparklePresets.length);
  }

  return nextIndex;
}

function CardTag({ tag }: { tag: CardTagValue }) {
  const sparklesRef = useRef<Array<HTMLSpanElement | null>>([]);
  const presetIndexesRef = useRef(tagSparkleBaseAngles.map(() => getRandomSparklePresetIndex()));

  function refreshSparkle(index: number) {
    const element = sparklesRef.current[index];
    if (!element) return;

    presetIndexesRef.current[index] = getRandomSparklePresetIndex(presetIndexesRef.current[index]);
    const style = sparklePresets[presetIndexesRef.current[index]][index];
    if (!style) return;

    element.style.left = String(style.left);
    element.style.top = String(style.top);
    element.style.setProperty("--sparkle-scale", String(style["--sparkle-scale"]));
  }

  return (
    <span className={`cardTag ${tag}`}>
      <span className="cardTagLabel">
        {tag}
        {Array.from({ length: 4 }, (_, index) => (
          <span
            className="cardTagSparkle"
            style={sparklePresets[presetIndexesRef.current[index]][index]}
            aria-hidden="true"
            key={index}
            ref={(element) => {
              sparklesRef.current[index] = element;
            }}
            onAnimationIteration={() => refreshSparkle(index)}
          />
        ))}
      </span>
    </span>
  );
}

const wandTipOffset = { x: 3, y: 5 };

async function copyText(text: string) {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  const isCopied = document.execCommand("copy");
  textarea.remove();

  if (!isCopied) {
    throw new Error("复制失败");
  }
}

function useMouseGlow(isModalOpen: boolean) {
  const cursorRef = useRef<HTMLDivElement | null>(null);
  const glowRef = useRef<HTMLSpanElement | null>(null);
  const activeCardRectRef = useRef<DOMRect | null>(null);
  const lastPointerSampleTimeRef = useRef(0);
  const pendingCursorOriginRef = useRef({
    x: window.innerWidth / 2 - wandTipOffset.x,
    y: window.innerHeight / 2 - wandTipOffset.y,
  });
  const animationFrameRef = useRef<number | null>(null);
  const idleTimerRef = useRef<number | null>(null);
  const isPointerIdleRef = useRef(true);
  const isModalOpenRef = useRef(isModalOpen);

  useEffect(() => {
    isModalOpenRef.current = isModalOpen;
  }, [isModalOpen]);

  useEffect(() => {
    if (!isModalOpen) {
      document.documentElement.classList.remove("modalOpen");
      return;
    }

    const previousOverflow = document.body.style.overflow;
    activeCardRectRef.current = null;
    document.documentElement.classList.add("modalOpen");
    document.body.style.overflow = "hidden";

    if (animationFrameRef.current !== null) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    return () => {
      document.documentElement.classList.remove("modalOpen");
      document.body.style.overflow = previousOverflow;
    };
  }, [isModalOpen]);

  useEffect(() => {
    if (
      !window.matchMedia("(pointer: fine)").matches ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    const attractionRadius = 130;
    const attractionStrength = 0.65;
    const pointerSampleInterval = 1000 / 30;

    function writePointerState() {
      const cursorOrigin = pendingCursorOriginRef.current;
      const tip = {
        x: cursorOrigin.x + wandTipOffset.x,
        y: cursorOrigin.y + wandTipOffset.y,
      };
      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate3d(${cursorOrigin.x}px, ${cursorOrigin.y}px, 0)`;
      }

      if (!isModalOpenRef.current) {
        let glow = tip;
        const rect = activeCardRectRef.current;

        if (rect) {
          const closestX = Math.max(rect.left, Math.min(tip.x, rect.right));
          const closestY = Math.max(rect.top, Math.min(tip.y, rect.bottom));
          const distance = Math.hypot(tip.x - closestX, tip.y - closestY);

          if (distance <= attractionRadius) {
            const center = {
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
            };
            glow = {
              x: tip.x + (center.x - tip.x) * attractionStrength,
              y: tip.y + (center.y - tip.y) * attractionStrength,
            };
          }
        }

        if (glowRef.current) {
          glowRef.current.style.transform = `translate3d(${glow.x}px, ${glow.y}px, 0) translate3d(-50%, -50%, 0)`;
        }
      }

      animationFrameRef.current = null;
    }

    function markPointerActive() {
      if (isPointerIdleRef.current) {
        document.documentElement.classList.remove("pointerIdle");
        isPointerIdleRef.current = false;
      }

      if (idleTimerRef.current !== null) {
        window.clearTimeout(idleTimerRef.current);
      }

      idleTimerRef.current = window.setTimeout(() => {
        document.documentElement.classList.add("pointerIdle");
        isPointerIdleRef.current = true;
        idleTimerRef.current = null;
      }, 1000);
    }

    function schedulePointerWrite(cursorOrigin: { x: number; y: number }) {
      pendingCursorOriginRef.current = cursorOrigin;
      if (animationFrameRef.current !== null) {
        return;
      }

      animationFrameRef.current = window.requestAnimationFrame(writePointerState);
    }

    function trackPointer(event: PointerEvent) {
      const now = window.performance.now();
      if (now - lastPointerSampleTimeRef.current < pointerSampleInterval) {
        return;
      }

      lastPointerSampleTimeRef.current = now;
      markPointerActive();
      schedulePointerWrite({
        x: event.clientX - wandTipOffset.x,
        y: event.clientY - wandTipOffset.y,
      });
    }

    document.documentElement.classList.add("pointerIdle");
    window.addEventListener("pointermove", trackPointer);

    return () => {
      window.removeEventListener("pointermove", trackPointer);
      document.documentElement.classList.remove("pointerIdle");

      if (idleTimerRef.current !== null) {
        window.clearTimeout(idleTimerRef.current);
        idleTimerRef.current = null;
      }

      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, []);

  const handleCardPointerEnter = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    if (isModalOpenRef.current) {
      return;
    }

    activeCardRectRef.current = event.currentTarget.getBoundingClientRect();
  }, []);

  const handleCardPointerLeave = useCallback(() => {
    activeCardRectRef.current = null;
  }, []);

  return {
    cursorRef,
    glowRef,
    handleCardPointerEnter,
    handleCardPointerLeave,
  };
}

function App() {
  const items = showcaseItems;
  const [selectedItem, setSelectedItem] = useState<ShowcaseItem | null>(null);
  const [selectedDocument, setSelectedDocument] = useState("");
  const [copiedItemId, setCopiedItemId] = useState<string | null>(null);
  const copiedResetTimerRef = useRef<number | null>(null);
  const isModalOpen = selectedItem !== null;
  const { cursorRef, glowRef, handleCardPointerEnter, handleCardPointerLeave } =
    useMouseGlow(isModalOpen);

  useEffect(() => {
    document.documentElement.className = "theme-dark";
  }, []);

  useEffect(() => {
    if (!selectedItem) {
      setSelectedDocument("");
      return;
    }

    let isCurrent = true;
    setSelectedDocument("正在加载文档...");

    fetchShowcaseDocument(selectedItem)
      .then((content) => {
        if (isCurrent) {
          setSelectedDocument(content);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setSelectedDocument("文档加载失败。");
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedItem]);

  async function copyCommand(item: ShowcaseItem) {
    await copyText(item.installCommand);
    setCopiedItemId(item.id);

    if (copiedResetTimerRef.current !== null) {
      window.clearTimeout(copiedResetTimerRef.current);
    }

    copiedResetTimerRef.current = window.setTimeout(() => {
      setCopiedItemId(null);
      copiedResetTimerRef.current = null;
    }, 1200);
  }

  useEffect(() => {
    return () => {
      if (copiedResetTimerRef.current !== null) {
        window.clearTimeout(copiedResetTimerRef.current);
      }
    };
  }, []);

  return (
    <main className={`shell ${isModalOpen ? "modalOpen" : ""}`}>
      <span className="skyStars" aria-hidden="true" />
      <span className="pointerGlow" ref={glowRef} aria-hidden="true" />
      <div className="magicCursor" ref={cursorRef} aria-hidden="true">
        <svg className="magicCursorWand" viewBox="0 0 24 24" fill="none">
          <g transform="translate(24 0) scale(-1 1)">
            <path d="m20.9 4.38-1.28-1.28a0.52 0.52 0 0 0-0.74 0L3.1 18.88a0.52 0.52 0 0 0 0 0.74l1.28 1.28a0.52 0.52 0 0 0 0.74 0L20.9 5.12a0.52 0.52 0 0 0 0-0.74Z" />
            <path d="m14.35 7.35 2.3 2.3" />
            <path d="M5 6v4" />
            <path d="M19 14v4" />
            <path d="M10 2v2" />
            <path d="M7 8H3" />
            <path d="M21 16h-4" />
            <path d="M11 3H9" />
          </g>
        </svg>
        <span className="sparkle sparkleOne" />
        <span className="sparkle sparkleTwo" />
        <span className="sparkle sparkleThree" />
      </div>
      <section className="hero">
        <p className="eyebrow">Ever-Evolving</p>
        <h1>Open Skills & MCP</h1>
        <p className="heroText">EOS. 部分 Skill 与 MCP 开源｜复制 · 一键安装</p>
      </section>

      <section className="cardGrid" aria-label="Skills and MCP">
        {items.map((item) => {
          const visualType = getCardVisualType(item.type);
          return (
          <article
            className={`showcaseCard ${visualType} ${item.tag ? "withTag" : ""}`}
            key={item.id}
            data-item-id={item.id}
            onPointerEnter={handleCardPointerEnter}
            onPointerLeave={handleCardPointerLeave}
            onClick={() => setSelectedItem(item)}
          >
            {item.tag && <CardTag tag={item.tag} />}
            <header className="cardHeader">
              <span className={`orb ${visualType}`}>{item.icon}</span>
              <h2>{item.name}</h2>
            </header>
            <div className="cardBody">
              <p>{item.shortIntro}</p>
            </div>
            <footer className="cardFooter">
              <code>{item.displayCommand}</code>
              <button
                className="magicBtn"
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  void copyCommand(item);
                }}
              >
                {copiedItemId === item.id ? "已复制" : "复制"}
              </button>
            </footer>
          </article>
          );
        })}
      </section>

      {selectedItem && (
        <div className="modalBackdrop" onClick={() => setSelectedItem(null)}>
          <section
            className={`detailModal ${getCardVisualType(selectedItem.type)}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="closeButton"
              type="button"
              aria-label="关闭详情"
              onClick={(event) => {
                event.stopPropagation();
                setSelectedItem(null);
              }}
            >
              x
            </button>
            <header className="detailHeader">
              <span className="detailType">{getTypeLabel(selectedItem.type)}</span>
              <h2 id="detail-title">{selectedItem.name}</h2>
            </header>
            <div className="modalCommand">
              <code>{selectedItem.displayCommand}</code>
              <button
                className="magicBtn"
                type="button"
                onClick={() => void copyCommand(selectedItem)}
              >
                {copiedItemId === selectedItem.id ? "已复制" : "复制命令"}
              </button>
            </div>
            <pre className="documentPreview">
              <code>{selectedDocument}</code>
            </pre>
          </section>
        </div>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
