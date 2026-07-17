import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import client, { formatError } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Buildings, Clock, Car, Check, ArrowLeft, ArrowRight, Plus, Trash } from "@phosphor-icons/react";

const TIMEZONES = [
  "America/Toronto", "America/New_York", "America/Chicago", "America/Denver",
  "America/Los_Angeles", "America/Vancouver", "America/Halifax", "Europe/London",
];
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const STEPS = [
  { n: 1, label: "Dealership", icon: Buildings },
  { n: 2, label: "Hours", icon: Clock },
  { n: 3, label: "Inventory", icon: Car },
];

const field = (v, set, key) => (e) => set({ ...v, [key]: e.target.value });

export default function OnboardingWizard() {
  const { org, refresh } = useAuth();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  const [details, setDetails] = useState({
    name: org?.name || "", phone: "", time_zone: "America/Toronto",
    location_name: "", address_line_1: "", city: "", province_state: "",
    postal_zip_code: "", loc_phone: "", loc_email: "",
  });
  const [hours, setHours] = useState({
    days: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: true, sunday: false },
    start_time: "09:00", end_time: "17:00",
  });
  const [vehicles, setVehicles] = useState([{ stock_number: "", make: "", model: "", year: "", price: "" }]);

  const toggleDay = (d) => setHours((h) => ({ ...h, days: { ...h.days, [d]: !h.days[d] } }));
  const setVeh = (i, key) => (e) =>
    setVehicles((rows) => rows.map((r, idx) => (idx === i ? { ...r, [key]: e.target.value } : r)));
  const addVeh = () => setVehicles((r) => [...r, { stock_number: "", make: "", model: "", year: "", price: "" }]);
  const removeVeh = (i) => setVehicles((r) => r.filter((_, idx) => idx !== i));

  const buildPayload = () => {
    const availability = DAYS.filter((d) => hours.days[d]).map((d) => ({
      day_of_week: d, start_time: hours.start_time, end_time: hours.end_time,
      appointment_type: "in_person_appraisal",
    }));
    const inventory = vehicles
      .filter((v) => v.make && v.model)
      .map((v) => ({
        stock_number: v.stock_number || undefined, make: v.make, model: v.model,
        year: v.year ? parseInt(v.year, 10) : undefined,
        price: v.price ? parseFloat(v.price) : undefined, status: "available",
      }));
    return {
      organization: { name: details.name, phone: details.phone, time_zone: details.time_zone },
      location: {
        name: details.location_name || details.name, address_line_1: details.address_line_1,
        city: details.city, province_state: details.province_state,
        postal_zip_code: details.postal_zip_code, phone: details.loc_phone,
        email: details.loc_email, time_zone: details.time_zone,
      },
      availability, inventory,
    };
  };

  const finish = async () => {
    setSaving(true);
    try {
      await client.post("/onboarding/complete", buildPayload());
      toast.success("Setup complete — welcome aboard!");
      await refresh();
    } catch (e) {
      toast.error(formatError(e?.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const skip = async () => {
    setSaving(true);
    try {
      await client.post("/onboarding/skip");
      toast.message("Setup skipped — you can finish it anytime in Settings.");
      await refresh();
    } catch (e) {
      toast.error(formatError(e?.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const canNext1 = details.name.trim().length > 0;

  return (
    <div
      data-testid="onboarding-wizard"
      className="dark fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto"
    >
      <div className="w-full max-w-2xl bg-card border border-border rounded-[6px] shadow-2xl my-8">
        {/* header */}
        <div className="px-6 lg:px-8 pt-7 pb-5 border-b border-border">
          <div className="text-xs font-mono-plex uppercase tracking-widest text-primary mb-1">Get started</div>
          <h1 className="font-head font-black text-2xl lg:text-3xl tracking-tight">Set up your dealership</h1>
          <p className="text-sm text-muted-foreground mt-1">
            A few quick details so your AI seller assistant is ready to book appointments.
          </p>
          {/* stepper */}
          <div className="flex items-center gap-2 mt-5">
            {STEPS.map((s, i) => {
              const active = s.n === step;
              const done = s.n < step;
              return (
                <div key={s.n} className="flex items-center gap-2 flex-1 last:flex-none">
                  <div
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-[4px] text-xs font-medium transition-colors duration-200 ${
                      active ? "bg-primary/15 text-primary"
                        : done ? "text-foreground" : "text-muted-foreground"
                    }`}
                  >
                    {done ? <Check size={16} weight="bold" /> : <s.icon size={16} weight="bold" />}
                    <span className="hidden sm:block">{s.label}</span>
                  </div>
                  {i < STEPS.length - 1 && <div className="h-px flex-1 bg-border" />}
                </div>
              );
            })}
          </div>
        </div>

        {/* body */}
        <div className="px-6 lg:px-8 py-6 space-y-4">
          {step === 1 && (
            <div className="space-y-4" data-testid="onboarding-step-details">
              <div>
                <Label>Dealership name *</Label>
                <Input data-testid="ob-org-name" value={details.name} onChange={field(details, setDetails, "name")}
                  placeholder="Prestige Auto Toronto" />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label>Phone</Label>
                  <Input data-testid="ob-org-phone" value={details.phone} onChange={field(details, setDetails, "phone")}
                    placeholder="+1-416-555-0142" />
                </div>
                <div>
                  <Label>Time zone</Label>
                  <select data-testid="ob-timezone" value={details.time_zone}
                    onChange={field(details, setDetails, "time_zone")}
                    className="flex h-10 w-full rounded-[4px] border border-border bg-background px-3 py-2 text-sm">
                    {TIMEZONES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>
              <div className="pt-2 border-t border-border">
                <div className="text-xs font-mono-plex uppercase tracking-widest text-muted-foreground mb-3">Primary location</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2">
                    <Label>Street address</Label>
                    <Input data-testid="ob-address" value={details.address_line_1}
                      onChange={field(details, setDetails, "address_line_1")} placeholder="1200 Front Street W" />
                  </div>
                  <div>
                    <Label>City</Label>
                    <Input data-testid="ob-city" value={details.city} onChange={field(details, setDetails, "city")} placeholder="Toronto" />
                  </div>
                  <div>
                    <Label>Province / State</Label>
                    <Input data-testid="ob-province" value={details.province_state}
                      onChange={field(details, setDetails, "province_state")} placeholder="ON" />
                  </div>
                  <div>
                    <Label>Postal / ZIP</Label>
                    <Input data-testid="ob-postal" value={details.postal_zip_code}
                      onChange={field(details, setDetails, "postal_zip_code")} placeholder="M5V 1J5" />
                  </div>
                  <div>
                    <Label>Location email</Label>
                    <Input data-testid="ob-loc-email" value={details.loc_email}
                      onChange={field(details, setDetails, "loc_email")} placeholder="sales@yourdealer.com" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5" data-testid="onboarding-step-hours">
              <p className="text-sm text-muted-foreground">
                Pick the days you accept appraisal appointments and your daily window. The AI only offers real, open slots.
              </p>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((d) => (
                  <button key={d} type="button" data-testid={`ob-day-${d}`} onClick={() => toggleDay(d)}
                    className={`px-3 py-2 rounded-[4px] text-sm font-medium capitalize transition-colors duration-200 border ${
                      hours.days[d] ? "bg-primary/15 border-primary/50 text-primary"
                        : "border-border text-muted-foreground hover:bg-secondary"
                    }`}>
                    {d.slice(0, 3)}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4 max-w-xs">
                <div>
                  <Label>Opens</Label>
                  <Input type="time" data-testid="ob-start" value={hours.start_time}
                    onChange={(e) => setHours({ ...hours, start_time: e.target.value })} />
                </div>
                <div>
                  <Label>Closes</Label>
                  <Input type="time" data-testid="ob-end" value={hours.end_time}
                    onChange={(e) => setHours({ ...hours, end_time: e.target.value })} />
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4" data-testid="onboarding-step-inventory">
              <p className="text-sm text-muted-foreground">
                Add a few vehicles to power inventory matching (optional). You can bulk-import via CSV later in Inventory.
              </p>
              <div className="space-y-2">
                {vehicles.map((v, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2 items-center">
                    <Input className="col-span-3" data-testid={`ob-veh-make-${i}`} value={v.make}
                      onChange={setVeh(i, "make")} placeholder="Make" />
                    <Input className="col-span-3" data-testid={`ob-veh-model-${i}`} value={v.model}
                      onChange={setVeh(i, "model")} placeholder="Model" />
                    <Input className="col-span-2" data-testid={`ob-veh-year-${i}`} value={v.year}
                      onChange={setVeh(i, "year")} placeholder="Year" />
                    <Input className="col-span-3" data-testid={`ob-veh-price-${i}`} value={v.price}
                      onChange={setVeh(i, "price")} placeholder="Price" />
                    <button type="button" onClick={() => removeVeh(i)} data-testid={`ob-veh-remove-${i}`}
                      className="col-span-1 flex justify-center text-muted-foreground hover:text-destructive transition-colors duration-200">
                      <Trash size={18} />
                    </button>
                  </div>
                ))}
              </div>
              <Button type="button" variant="outline" size="sm" onClick={addVeh} data-testid="ob-add-vehicle">
                <Plus size={16} className="mr-1" /> Add vehicle
              </Button>
            </div>
          )}
        </div>

        {/* footer */}
        <div className="px-6 lg:px-8 py-4 border-t border-border flex items-center justify-between gap-3">
          <button type="button" onClick={skip} disabled={saving} data-testid="onboarding-skip"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-200">
            Skip for now
          </button>
          <div className="flex items-center gap-2">
            {step > 1 && (
              <Button type="button" variant="outline" onClick={() => setStep(step - 1)} disabled={saving} data-testid="onboarding-back">
                <ArrowLeft size={16} className="mr-1" /> Back
              </Button>
            )}
            {step < 3 ? (
              <Button type="button" onClick={() => setStep(step + 1)} disabled={step === 1 && !canNext1} data-testid="onboarding-next">
                Next <ArrowRight size={16} className="ml-1" />
              </Button>
            ) : (
              <Button type="button" onClick={finish} disabled={saving} data-testid="onboarding-finish">
                {saving ? "Saving…" : "Finish setup"} <Check size={16} className="ml-1" weight="bold" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
