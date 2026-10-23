import howItWorks from "../lib/howItWorksSteps.json";

/** The signed-out walkthrough: phone screenshots of the real app (fake mode), in order, with one line each.
 * Side by side on wide screens; a sideways-swiping row on phones. `scripts/how_it_works.py` makes the images. */
export function HowItWorks() {
  return (
    <section aria-labelledby="how-it-works" className="mb-10" data-how-it-works>
      <div className="mb-4 text-center">
        <h2 id="how-it-works" className="text-xl font-semibold tracking-tight">
          {howItWorks.heading}
        </h2>
        <p className="mt-1 text-sm text-muted">{howItWorks.lead}</p>
      </div>
      {/* Focusable so keyboard users can scroll the row when it doesn't fit. */}
      <ol
        tabIndex={0}
        aria-label="Steps"
        className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0 lg:grid lg:grid-cols-6 lg:overflow-visible"
      >
        {howItWorks.steps.map((step, i) => (
          <li key={step.image} className="w-48 shrink-0 snap-center lg:w-auto">
            <div className="overflow-hidden rounded-[1.25rem] border-4 border-line bg-surface shadow-sm">
              <img
                src={`/how-it-works/${step.image}`}
                alt={step.alt}
                width={390}
                height={844}
                loading="lazy"
                className="block h-auto w-full"
              />
            </div>
            <p className="mt-2 text-center text-sm leading-snug">
              <span className="font-semibold text-accent">{i + 1}.</span> {step.caption}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
