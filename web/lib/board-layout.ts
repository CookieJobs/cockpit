/**
 * MainBoard's responsive shell classes.
 *
 * On a phone, projects are the default surface and chat becomes a temporary
 * full-screen workspace.  Keeping the rule here makes the desktop/mobile
 * contract independently testable instead of burying it in JSX branches.
 */
export function getChatPanelClassName(): string {
  return "fixed inset-0 z-30 flex flex-col bg-bg md:static md:z-auto md:w-[35%] md:min-w-[360px] md:max-w-[640px]";
}

export function getChatLauncherClassName(): string {
  return "fixed bottom-4 right-4 z-20 h-11 w-11 rounded-full border border-border bg-bg-secondary shadow-lg hover:bg-bg-tertiary transition flex items-center justify-center text-fg-muted hover:text-fg group md:static md:h-auto md:w-11 md:rounded-none md:shadow-none md:border-0 md:border-l md:flex-col md:items-center md:justify-start md:pt-4 md:gap-3";
}
