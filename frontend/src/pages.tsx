import { Link } from "react-router";

import { PageHeader } from "./components/PageHeader";
import { linkClass } from "./components/ui";

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <p className="text-fg-muted">
        This page does not exist.{" "}
        <Link to="/filters" className={linkClass}>
          Go to the filters
        </Link>
        .
      </p>
    </>
  );
}
