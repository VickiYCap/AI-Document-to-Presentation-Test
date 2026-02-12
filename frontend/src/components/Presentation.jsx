import { useEffect, useRef } from "react";
import "./Presentation.css";

// ✅ Recommended ESM imports for pdfjs-dist
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import workerSrc from "pdfjs-dist/build/pdf.worker.mjs?url";

// Configure worker (must be done before any getDocument call)
GlobalWorkerOptions.workerSrc = workerSrc;

function Presentation() {
  const pagesContainerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let destroyed = false;

    const renderPdf = async () => {
      try {
        // ✅ Give the worker a tick to fully initialize
        await new Promise((r) => setTimeout(r, 0));

        // Load the PDF
        const loadingTask = getDocument("/Updated_Presentation.pdf");
        const pdf = await loadingTask.promise;

        // Optional: clear previous content (e.g., if re-mounted)
        if (pagesContainerRef.current) {
          pagesContainerRef.current.innerHTML = "";
        }

        // Helper to render a single page with a safe scale
        const renderPage = async (pageNum, attempt = 1) => {
          if (cancelled) return;

          const page = await pdf.getPage(pageNum);

          // Base scale
          let scale = 1.2;
          let viewport = page.getViewport({ scale });

          // ✅ Clamp for oversized pages to prevent silent canvas failure
          const MAX_DIM = 2200; // tweak if needed
          if (viewport.width > MAX_DIM || viewport.height > MAX_DIM) {
            const factor = Math.min(MAX_DIM / viewport.width, MAX_DIM / viewport.height);
            scale = Math.max(0.5, Math.min(scale * factor, 1.2)); // keep scale reasonable
            viewport = page.getViewport({ scale });
          }

          // Create canvas
          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d", { alpha: false });

          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.style.width = "100%";
          canvas.style.height = "auto";
          canvas.style.margin = "16px 0";
          canvas.setAttribute("data-page", String(pageNum));

          // Render BEFORE appending
          try {
            await page.render({ canvasContext: ctx, viewport }).promise;
          } catch (err) {
            // Rare: page 1 occasionally fails on first try in some bundlers
            if (pageNum === 1 && attempt < 2 && !cancelled) {
              console.warn("Retrying page 1 render once due to transient failure:", err);
              await new Promise((r) => setTimeout(r, 0));
              return renderPage(pageNum, attempt + 1);
            }
            throw err;
          }

          if (!cancelled && pagesContainerRef.current) {
            pagesContainerRef.current.appendChild(canvas);
          }
        };

        // Render pages sequentially
        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          if (cancelled) break;
          await renderPage(pageNum);
        }

        // Clean up PDF loading task if effect was cancelled before finishing
        if (cancelled && !destroyed) {
          try {
            await pdf.destroy();
            destroyed = true;
          } catch {
            /* ignore */
          }
        }
      } catch (err) {
        console.error("PDF ERROR:", err);
      }
    };

    renderPdf();

    // ✅ StrictMode-safe cleanup: don't instantly wipe while a render may still be in-flight
    return () => {
      cancelled = true;
      // Small timeout prevents tearing down between the two StrictMode mounts
      setTimeout(() => {
        if (pagesContainerRef.current) {
          pagesContainerRef.current.innerHTML = "";
        }
      }, 50);
    };
  }, []);

  return (
    <div className="presentation-container">
      <div ref={pagesContainerRef} className="pdf-pages" />
    </div>
  );
}

export default Presentation;