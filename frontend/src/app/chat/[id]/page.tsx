"use client";

import { use } from "react";
import ChatInterface from "@/components/ChatInterface";

export default function ChatPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const characterId = parseInt(id, 10);

  if (isNaN(characterId)) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-red-500">Invalid character ID</p>
      </div>
    );
  }

  return <ChatInterface characterId={characterId} />;
}

