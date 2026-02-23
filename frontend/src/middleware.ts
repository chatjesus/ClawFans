import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Only hard-protect routes that truly require an account.
// Chat is intentionally public — users get prompted inline when they need memory/sync.
const isProtectedRoute = createRouteMatcher([
  "/settings",  // Platform config requires auth
]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and static files
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
