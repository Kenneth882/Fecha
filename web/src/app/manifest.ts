import type { MetadataRoute } from "next";

// Makes the app installable. There's no service worker, so nothing works offline yet.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CramPlan",
    short_name: "CramPlan",
    description: "A day-by-day cram plan for one real event, by one fixed date.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#1d4ed8",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
