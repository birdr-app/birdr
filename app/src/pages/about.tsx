import { FormattedMessage } from "react-intl";
import { CmsPage } from "./cms-page";

export const AboutPage = () => (
  <CmsPage
    slug="about"
    showBackToHelp
    headerTitle={<FormattedMessage id="about birdr" defaultMessage="About Motmot" />}
  />
);
