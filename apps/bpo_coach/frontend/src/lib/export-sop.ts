import { ApiError, screenshotUrl } from "./api";
import {
  createSopDocument,
  sopFilename,
  type SopScreenshot,
  type SopSource,
} from "./sop-document";

async function loadScreenshot(assetId: string): Promise<SopScreenshot> {
  const response = await fetch(await screenshotUrl(assetId), {
    credentials: "same-origin",
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      "The screenshot could not be downloaded.",
      response.status,
    );
  }
  const url = URL.createObjectURL(await response.blob());
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    // Normalize PNG, JPEG, WebP and seeded SVG screenshots to a Word-compatible image.
    const scale = Math.min(
      1800 / image.naturalWidth,
      1800 / image.naturalHeight,
      1,
    );
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("The screenshot could not be prepared.");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const png = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) =>
          blob
            ? resolve(blob)
            : reject(new Error("The screenshot could not be prepared.")),
        "image/png",
      );
    });
    return {
      data: new Uint8Array(await png.arrayBuffer()),
      width: canvas.width,
      height: canvas.height,
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function exportSop(source: SopSource) {
  const screenshots = new Map<string, SopScreenshot>();
  // Load once per asset and limit simultaneous image decoding for large scenarios.
  for (const [index, step] of source.content.steps.entries()) {
    if (!step.assetId || screenshots.has(step.assetId)) continue;
    try {
      screenshots.set(step.assetId, await loadScreenshot(step.assetId));
    } catch {
      throw new Error(
        `Could not load the screenshot for step ${index + 1} (${step.title || "Untitled step"}). Please retry export.`,
      );
    }
  }
  const blob = await createSopDocument(source, screenshots);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = sopFilename(source.content.title);
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Give the browser time to start consuming the Blob before releasing it.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
