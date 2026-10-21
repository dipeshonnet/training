import {
  AlignmentType,
  Document,
  HeadingLevel,
  ImageRun,
  Packer,
  Paragraph,
  TextRun,
} from "docx";
import type { Process, ScenarioContent } from "../shared/types";

export interface SopSource {
  content: ScenarioContent;
  process?: Pick<Process, "name" | "client">;
  revision?: number;
  unsaved?: boolean;
}

export interface SopScreenshot {
  data: Uint8Array;
  width: number;
  height: number;
}

const paragraphs = (text: string) =>
  text.split(/\r\n|\r|\n/).map((line) => new Paragraph({ text: line }));

const heading = (text: string) =>
  new Paragraph({ text, heading: HeadingLevel.HEADING_1 });

const labeled = (label: string, text: string) =>
  new Paragraph({
    children: [
      new TextRun({ text: label + ": ", bold: true }),
      new TextRun(text),
    ],
  });

export function sopFilename(title: string) {
  const name = title
    .normalize("NFKC")
    .replace(/[<>:"/\\|?*\u0000-\u001f\u007f]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 100)
    .replace(/[. ]+$/, "");
  return (name || "Scenario") + " - SOP.docx";
}

export async function createSopDocument(
  source: SopSource,
  screenshots: ReadonlyMap<string, SopScreenshot>,
) {
  const { content, process } = source;
  const children: Paragraph[] = [
    new Paragraph({
      text: "STANDARD OPERATING PROCEDURE",
      style: "Subtitle",
    }),
    new Paragraph({ text: content.title, heading: HeadingLevel.TITLE }),
  ];
  if (process) {
    children.push(labeled("Process", process.name));
    if (process.client) children.push(labeled("Client", process.client));
  }
  children.push(
    labeled(
      "Work type",
      content.office === "front" ? "Front office" : "Back office",
    ),
    labeled(
      "Source",
      source.unsaved
        ? "Unsaved draft"
        : source.revision
          ? "Draft revision " + source.revision
          : "Draft",
    ),
    labeled(
      "Exported",
      new Date().toLocaleString("en", {
        dateStyle: "medium",
        timeStyle: "short",
      }),
    ),
  );
  for (const [title, text] of [
    ["Purpose and scope", content.brief],
    ["Reference instructions", content.reference],
    ["Expected outcome", content.outcome],
  ]) {
    if (text.trim()) children.push(heading(title), ...paragraphs(text));
  }
  if (
    content.office === "front" &&
    (content.customerName || content.persona || content.opening)
  ) {
    children.push(heading("Customer context"));
    if (content.customerName)
      children.push(labeled("Customer", content.customerName));
    if (content.persona) children.push(...paragraphs(content.persona));
    if (content.opening)
      children.push(labeled("Opening message", content.opening));
  }

  if (!content.steps.length) {
    children.push(
      heading("Procedure"),
      new Paragraph("No procedure steps configured."),
    );
  }
  content.steps.forEach((step, index) => {
    children.push(
      new Paragraph({
        text: `Procedure - step ${index + 1} of ${content.steps.length}`,
        heading: HeadingLevel.HEADING_1,
        pageBreakBefore: true,
      }),
      new Paragraph({
        text: step.title || "Untitled step",
        heading: HeadingLevel.HEADING_2,
      }),
    );
    if (step.critical)
      children.push(
        labeled("Critical check", "This step must be completed correctly."),
      );
    children.push(...paragraphs(step.instructions));
    if (step.assetId) {
      const screenshot = screenshots.get(step.assetId);
      if (!screenshot)
        throw new Error(
          `Screenshot missing for step ${index + 1}. Please retry export.`,
        );
      const scale = Math.min(
        620 / screenshot.width,
        340 / screenshot.height,
        1,
      );
      children.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new ImageRun({
              type: "png",
              data: screenshot.data,
              transformation: {
                width: Math.round(screenshot.width * scale),
                height: Math.round(screenshot.height * scale),
              },
              altText: {
                title: step.title || `Step ${index + 1}`,
                description: `Application screenshot for procedure step ${index + 1}`,
                name: `Step ${index + 1} screenshot`,
              },
            }),
          ],
        }),
      );
    }
    const required = step.hotspots.filter((action) => action.correct);
    if (required.length) {
      children.push(
        new Paragraph({
          text: "Required actions",
          heading: HeadingLevel.HEADING_3,
        }),
      );
      for (const action of required) {
        children.push(
          labeled(action.type === "input" ? "Enter" : "Select", action.label),
        );
        if (action.type === "input" && action.accepted.length)
          children.push(
            labeled("Accepted input", action.accepted.join(" or ")),
          );
        if (action.critical)
          children.push(
            labeled(
              "Critical check",
              "This action must be completed correctly.",
            ),
          );
      }
    }
    const avoid = step.hotspots.filter((action) => !action.correct);
    if (avoid.length) {
      children.push(
        new Paragraph({
          text: "Actions to avoid",
          heading: HeadingLevel.HEADING_3,
        }),
      );
      for (const action of avoid)
        children.push(
          labeled(
            action.critical ? "Critical - do not" : "Do not",
            action.label,
          ),
        );
    }
    if (step.hint) children.push(labeled("Guidance", step.hint));
  });

  return Packer.toBlob(
    new Document({
      creator: "AI Coach",
      title: content.title + " - Standard Operating Procedure",
      description: "Standard operating procedure for " + content.title,
      styles: {
        default: {
          document: {
            run: { font: "Arial", size: 22, color: "24382D" },
            paragraph: { spacing: { after: 140, line: 276 } },
          },
          title: {
            run: { size: 42, bold: true, color: "284F3D" },
            paragraph: { spacing: { after: 300 } },
          },
          heading1: {
            run: { size: 28, bold: true, color: "284F3D" },
            paragraph: { spacing: { before: 280, after: 160 }, keepNext: true },
          },
          heading2: {
            run: { size: 25, bold: true, color: "284F3D" },
            paragraph: { spacing: { after: 160 }, keepNext: true },
          },
          heading3: {
            run: { size: 22, bold: true },
            paragraph: { spacing: { before: 160, after: 120 }, keepNext: true },
          },
        },
      },
      sections: [
        {
          properties: {
            page: {
              size: { width: 11906, height: 16838 },
              margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 },
            },
          },
          children,
        },
      ],
    }),
  );
}
