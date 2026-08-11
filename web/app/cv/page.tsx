import { redirect } from "next/navigation";

/** Compatibility route: all CV output now uses the shared output center. */
export default function CvPage() {
  redirect("/report?type=cv&range=all");
}
