import { ExternalLink } from "../../components/ui";

export function TelegramHelp() {
  return (
    <details className="rounded-lg border border-line bg-surface-muted/50 px-4 py-3">
      <summary className="cursor-pointer font-semibold">
        How do I get the bot token and chat ID?
      </summary>
      <ol className="mt-3 list-decimal space-y-2 pl-5 text-fg-muted">
        <li>
          In Telegram, open a chat with <strong>@BotFather</strong>, send <code>/newbot</code> and
          follow the steps. BotFather replies with the <strong>bot token</strong> (looks like{" "}
          <code>123456789:AAH...</code>). See the{" "}
          <ExternalLink href="https://core.telegram.org/bots/features#botfather">
            Telegram documentation
          </ExternalLink>
          .
        </li>
        <li>
          Open a chat with your new bot and send it any message. A bot cannot start a conversation
          on its own. For a group, add the bot to the group and write a message there.
        </li>
        <li>
          Open <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> in your browser
          (replace <code>&lt;TOKEN&gt;</code> with the bot token) and copy the number after{" "}
          <code>&quot;chat&quot;:&#123;&quot;id&quot;:</code>. That is the <strong>chat ID</strong>.
          Group IDs are negative. The list only keeps recent messages: if it is empty, send the bot
          another message and reload.
        </li>
        <li>
          Enter both below and use <strong>Send test message</strong> before saving.
        </li>
      </ol>
      <p className="mt-3 text-sm text-fg-subtle">
        A username (like <code>@yourname</code>) does not work as chat ID. Only public channels can
        be addressed as <code>@channelname</code>, and the bot must be an admin there.
      </p>
    </details>
  );
}
