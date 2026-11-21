import { Navigate, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { EditChannelPage, NewChannelPage } from "./features/channels/ChannelEditPage";
import { ChannelsPage } from "./features/channels/ChannelsPage";
import { EditFilterPage, NewFilterPage } from "./features/filters/FilterEditPage";
import { FiltersPage } from "./features/filters/FiltersPage";
import { AlertsPage } from "./features/alerts/AlertsPage";
import { StatusPage } from "./features/status/StatusPage";
import { NotFoundPage } from "./pages";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/filters" replace />} />
        <Route path="filters" element={<FiltersPage />} />
        <Route path="filters/new" element={<NewFilterPage />} />
        <Route path="filters/:filterId" element={<EditFilterPage />} />
        <Route path="channels" element={<ChannelsPage />} />
        <Route path="channels/new" element={<NewChannelPage />} />
        <Route path="channels/:channelId" element={<EditChannelPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
