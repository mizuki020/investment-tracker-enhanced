import { motion } from "framer-motion";
import { NumberTicker } from "@/components/magicui/number-ticker";

export function Statistics() {
  const stats = [
    { number: 15, label: "years of experience", prefix: "", suffix: "+" },
    { number: 50, label: "team members", prefix: "", suffix: "" },
    { number: 500, label: "clients served", prefix: "", suffix: "+" },
  ];

  return (
    <section className="bg-white py-20">
      <div className="container mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-12">
          {stats.map((stat, index) => (
            <motion.div
              key={index}
              className="text-left"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
            >
              <span className="text-6xl font-bold text-gray-900 mb-2">{stat.prefix}</span>
              <NumberTicker className="text-6xl font-bold text-gray-900 mb-2" value={stat.number} />
              <span className="text-6xl font-bold text-gray-900 mb-2">{stat.suffix}</span>
              <div className="text-gray-600 text-lg">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
