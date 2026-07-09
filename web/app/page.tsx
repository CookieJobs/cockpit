"use client";

import { useState } from "react";
import { MainBoard } from "@/components/MainBoard";

export default function HomePage() {
  const [refreshKey, setRefreshKey] = useState(0);
  return <MainBoard refreshKey={refreshKey} />;
}
