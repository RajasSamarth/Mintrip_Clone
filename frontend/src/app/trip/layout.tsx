// Trip pages inherit the root layout (html/body + Header).
// A nested layout must never render its own <html>/<body>; doing so broke
// client-side navigation and left the app blank until a full refresh.
export default function TripLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
