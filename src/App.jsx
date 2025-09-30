import { BrowserRouter as Router } from "react-router-dom";
import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import ScrollToAnchor from "@/components/ScrollToAnchor";
import { Hero } from "@/components/Hero";
import { About } from "@/components/About";
import { Statistics } from "@/components/Statistics";
import { Team } from "@/components/Team";
import { Services } from "@/components/Services";
import { Testimonials } from "@/components/Testimonials";
import { LocationsWithBanner } from "@/components/LocationsBanner";

function App() {
  return (
    <Router>
      <ScrollToAnchor />
      <div className="min-h-screen bg-white flex flex-col">
        <Navigation />
        <main className="flex-grow">
          <Hero />
          <About />
          <Statistics />
          <Team />
          <Services />
          <Testimonials />
          <LocationsWithBanner />
        </main>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
