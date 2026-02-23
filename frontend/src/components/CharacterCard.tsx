"use client";

import Link from "next/link";
import type { CharacterCard as CharacterCardType } from "@/lib/api";

function getAvatarGradient(name: string): string {
  const gradients = [
    "from-rose-700 to-red-900",
    "from-rose-700 to-pink-900",
    "from-pink-700 to-rose-900",
    "from-red-800 to-rose-900",
    "from-pink-600 to-red-800",
    "from-rose-600 to-pink-900",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return gradients[Math.abs(hash) % gradients.length];
}

interface Props {
  character: CharacterCardType;
}

export default function CharacterCard({ character }: Props) {
  const tags = character.tags
    ? character.tags.split(",").map((t) => t.trim())
    : [];
  const hasNSFW = tags.some((t) => t.toUpperCase() === "NSFW");
  const visibleTags = tags.filter((t) => t.toUpperCase() !== "NSFW").slice(0, 2);

  return (
    <Link href={`/chat/${character.id}`}>
      <div
        className="rounded-2xl overflow-hidden card-hover-lift cursor-pointer h-full flex flex-col border"
        style={{ borderColor: "var(--card-border)", background: "var(--card-bg)" }}
      >
        {/* Image area */}
        <div className="relative aspect-[3/4] overflow-hidden">
          {character.avatar_url ? (
            <img
              src={character.avatar_url}
              alt={character.name}
              className="w-full h-full object-cover object-top"
            />
          ) : (
            <div className={`w-full h-full bg-gradient-to-br ${getAvatarGradient(character.name)} flex items-center justify-center`}>
              <span className="text-6xl font-bold text-white/20">{character.name.charAt(0)}</span>
            </div>
          )}

          {/* Bottom fade */}
          <div className="absolute inset-x-0 bottom-0 h-2/3 img-gradient-overlay" />

          {/* NSFW badge */}
          {hasNSFW && (
            <div className="absolute top-2.5 right-2.5 nsfw-tag px-1.5 py-0.5 rounded">
              NSFW
            </div>
          )}

          {/* Name + stats overlaid */}
          <div className="absolute bottom-0 inset-x-0 px-3 pb-3">
            <div className="flex items-end justify-between gap-2">
              <div className="min-w-0">
                <h3 className="font-bold text-white text-sm truncate drop-shadow">
                  {character.name}
                </h3>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-white/55">&#128172; {character.message_count}</span>
                  <span className="text-[10px] text-white/55">&#10024; {character.star_count}</span>
                </div>
              </div>
              <div className="flex gap-1 flex-shrink-0">
                {visibleTags.map((tag) => (
                  <span
                    key={tag}
                    className="px-1.5 py-0.5 rounded text-[9px] font-medium backdrop-blur-sm"
                    style={{ background: "rgba(232, 96, 122, 0.28)", color: "#f4b8c4" }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Description */}
        <div className="px-3 py-2.5 flex-1">
          <p className="text-xs line-clamp-2 leading-relaxed" style={{ color: "var(--muted)" }}>
            {character.description}
          </p>
        </div>
      </div>
    </Link>
  );
}
