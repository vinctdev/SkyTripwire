// Small shared layout, form and feedback components. Colors come from the design tokens in
// index.css (bg-surface, text-fg-muted, border-line, ...), not from Tailwind's palette.
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-55";

const BUTTON_VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover",
  secondary: "border border-line-strong bg-surface text-fg hover:bg-surface-muted",
  danger: "bg-danger text-danger-fg hover:bg-danger-hover",
  ghost: "text-fg-muted hover:bg-surface-muted hover:text-fg",
};

/** Button styles, also for links that look like buttons (react-router `Link`). */
export function buttonClass(variant: Variant = "secondary"): string {
  return `${BUTTON_BASE} ${BUTTON_VARIANTS[variant]}`;
}

export function Button({
  variant = "secondary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button type={type} className={`${buttonClass(variant)} ${className}`} {...props} />;
}

/** Bordered panel used for list rows and page sections. */
export function Card({
  as: Tag = "div",
  className = "",
  children,
}: {
  as?: "div" | "li" | "section";
  className?: string;
  children: ReactNode;
}) {
  return (
    <Tag className={`rounded-xl border border-line bg-surface p-5 shadow-xs ${className}`}>
      {children}
    </Tag>
  );
}

const BADGE_TONES = {
  neutral: "bg-surface-muted text-fg-muted",
  info: "bg-info-soft text-info-text",
  success: "bg-success-soft text-success-text",
  warning: "bg-warning-soft text-warning-text",
  danger: "bg-danger-soft text-danger-text",
  alarm: "bg-danger text-danger-fg",
} as const;

export type BadgeTone = keyof typeof BADGE_TONES;

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const controlClass =
  "w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-base text-fg placeholder:text-fg-subtle focus:border-accent focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent aria-[invalid=true]:border-danger";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={controlClass} {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={controlClass} {...props} />;
}

/** Label, control, optional hint and error message. `id` must match the control's id. */
export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-semibold">
        {label}
      </label>
      {children}
      {hint && <p className="text-sm text-fg-subtle">{hint}</p>}
      {error && (
        <p id={`${id}-error`} className="text-sm font-medium text-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}

export function Checkbox({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="flex items-center gap-2.5">
      <input
        id={id}
        type="checkbox"
        className="size-4 accent-accent"
        checked={checked}
        onChange={(e) => {
          onChange(e.target.checked);
        }}
      />
      {label}
    </label>
  );
}

const NOTICE_TONES = {
  info: "border-info-line bg-info-soft text-info-text",
  success: "border-success-line bg-success-soft text-success-text",
  error: "border-danger-line bg-danger-soft text-danger-text",
} as const;

export function Notice({
  tone = "info",
  children,
}: {
  tone?: keyof typeof NOTICE_TONES;
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-lg border px-4 py-3 ${NOTICE_TONES[tone]}`}
    >
      {children}
    </div>
  );
}

/** Text link inside the app (react-router `Link`) or to another site. */
export const linkClass =
  "font-medium text-accent-text underline decoration-1 underline-offset-2 hover:decoration-2";

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={linkClass}>
      {children}
    </a>
  );
}

/** Small "Loading..." line shared by the pages. */
export function Loading() {
  return <p className="text-fg-subtle">Loading...</p>;
}
